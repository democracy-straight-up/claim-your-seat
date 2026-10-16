import json
from moda.housekeeping import remove_second_link_member_as_delegate
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.db import transaction
from succession_notifications import (
    post_succession_update,
    user_display_name,
)
from moda import models 
from moda import serializers


class ModaConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.moda_name = self.scope['url_route']['kwargs']['moda_name']
        self.user_name = self.scope['url_route']['kwargs']['user_name']
        self.room_name =  self.moda_name
        if not await self.is_authorized_member(user):
            await self.close(code=4403)
            return
        # Join room group
        await self.channel_layer.group_add(self.room_name, self.channel_name)

        # Fetch existing circle members using database_sync_to_async
        members = {'status':"success",'message':'listed all', "action":"init",
                   'member_list': await self.get_members(),
                   'vote_outs': await self.get_vote_outs(),
                   'vote_ins': await self.get_vote_ins(),
                   'put_forwards': await self.get_put_forwards()}
        
        # Accept the WebSocket connection
        await self.accept()

        # Send initial Circle members to the connected client
        await self.send(text_data=json.dumps(members))

    # when a member of the room leaves the room
    async def disconnect(self, close_code):
        # Remove the client from the room (channel group)
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

        # Your custom disconnect logic here
        await self.send(text_data=json.dumps({"status": "disconnecting", "message": "Goodbye!"}))

        # Call the parent class disconnect method
        await super().disconnect(close_code)

    @database_sync_to_async
    def is_authorized_member(self, user):
        return models.ModaMembers.objects.filter(
            moda__code=self.moda_name,
            user=user,
            is_member=True,
        ).exists()
    @database_sync_to_async
    def get_members(self):
        memberslist = models.ModaMembers.objects.filter(moda__code = self.moda_name)
        members = serializers.ModaMembersSerializer(memberslist, many=True)
        return members.data

    @database_sync_to_async
    def get_vote_ins(self):
        instances = models.VoteInModaMember.objects.filter(moda__code=self.moda_name)
        serialize = serializers.VoteInModaMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def get_vote_outs(self):
        instances = models.VoteOutModaMember.objects.filter(moda__code=self.moda_name)
        serialize = serializers.VoteOutModaMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def get_put_forwards(self):
        instances = models.PutFarwardModaMember.objects.filter(moda__code=self.moda_name)
        serialize = serializers.PutFarwardModaMemberSerializer(instances, many=True)
        return serialize.data
    
    @database_sync_to_async
    def member_vote_out(self, data):
        """ Vote for member out. If the majority of the members agree on removing this member,
        she/he shall be removed.
        """
        try:
            voter = User.objects.get(username=data["voter"])
            moda = models.ModaModel.objects.get(
                code=self.moda_name,
            )
            member = models.ModaMembers.objects.get(
                pk=data["member"],
                moda=moda,
                is_member=True,
            )
            actor = self.scope["user"]

            actor_membership = models.ModaMembers.objects.filter(
                user=actor,
                moda=moda,
                is_member=True,
            ).first()

            voter_is_member = models.ModaMembers.objects.filter(
                user=voter,
                moda=moda,
                is_member=True,
            ).exists()

            if (
                actor_membership is None
                or not voter_is_member
                or (
                    actor.pk != voter.pk
                    and not actor_membership.is_delegate
                )
            ):
                return {
                    "status": "error",
                    "action": "vote_out",
                    "message": "Not authorized to cast this vote.",
                    "user": serializers.UserSerializer(actor).data,
                }
            with transaction.atomic():
                votes_before = models.VoteOutModaMember.objects.filter(
                    candidate=member,
                    moda=moda,
                ).count()

                total_members = models.ModaMembers.objects.filter(
                    moda=moda,
                    is_member=True,
                ).count()
                majority_required = total_members // 2 + 1

                candidate_name = user_display_name(member.user)

                instance, created = (
                    models.VoteOutModaMember.objects.get_or_create(
                        voter=voter,
                        candidate=member,
                        moda=moda,
                        defaults={"agent": actor},
                    )
                )

                if created:
                    actor_name = user_display_name(actor)
                    voter_name = user_display_name(voter)

                    if actor.pk == voter.pk:
                        actor_description = actor_name
                    else:
                        actor_description = (
                            f"{actor_name}, acting as "
                            f"{voter_name}'s agent,"
                        )

                    post_succession_update(
                        message_model=models.ModaBackNForthChat,
                        group_field="moda",
                        group=moda,
                        message=(
                            f"Housekeeping: {actor_description} "
                            f"voted to expel {candidate_name}. "
                            f"Current tally: {votes_before + 1} "
                            f"of {majority_required} votes required."
                        ),
                    )
                    if (
                        votes_before + 1 >= majority_required
                        and not models.ModaMembers.objects.filter(
                            pk=member.pk,
                            moda=moda,
                        ).exists()
                    ):
                        post_succession_update(
                            message_model=models.ModaBackNForthChat,
                            group_field="moda",
                            group=moda,
                            message=(
                                f"Housekeeping: {candidate_name} was "
                                f"removed from the Second Link after "
                                f"receiving the required majority."
                            ),
                        )
            serialized = serializers.VoteOutModaMemberSerializer(instance)
            vote = serializers.UserSerializer(voter)

            return {
                "status": "success",
                "action": "vote_out",
                "message": "voted out successfully.",
                "user": vote.data,
                "instance": serialized.data,
            }
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_out", "message": "Could not vote out.","user":vote.data}
        
    @database_sync_to_async
    def undo_vote_out(self, data):
        """removing the vote of the member (undoing the voting out)"""
        try:
            voter = User.objects.get(username=data["voter"])
            moda = models.ModaModel.objects.get(code=self.moda_name)
            member = models.ModaMembers.objects.get(
                pk=data["member"],
                moda=moda,
            )

            actor = self.scope["user"]

            actor_membership = models.ModaMembers.objects.filter(
                user=actor,
                moda=moda,
                is_member=True,
            ).first()

            voter_is_member = models.ModaMembers.objects.filter(
                user=voter,
                moda=moda,
                is_member=True,
            ).exists()

            if (
                actor_membership is None
                or not voter_is_member
                or (
                    actor.pk != voter.pk
                    and not actor_membership.is_delegate
                )
            ):
                return {
                    "status": "error",
                    "action": "undo_vote_out",
                    "message": "Not authorized to withdraw this vote.",
                    "user": serializers.UserSerializer(actor).data,
                }

            with transaction.atomic():
                instance = models.VoteOutModaMember.objects.get(
                    voter=voter,
                    candidate=member,
                    moda=moda,
                )

                serialized_data = (
                    serializers.VoteOutModaMemberSerializer(instance).data
                )

                actor_name = user_display_name(actor)
                voter_name = user_display_name(voter)
                candidate_name = user_display_name(member.user)

                total_members = models.ModaMembers.objects.filter(
                    moda=moda,
                    is_member=True,
                ).count()
                majority_required = total_members // 2 + 1

                instance.delete()

                remaining_votes = models.VoteOutModaMember.objects.filter(
                    candidate=member,
                    moda=moda,
                ).count()

                if actor.pk == voter.pk:
                    actor_description = actor_name
                else:
                    actor_description = (
                        f"{actor_name}, acting as "
                        f"{voter_name}'s agent,"
                    )

                post_succession_update(
                    message_model=models.ModaBackNForthChat,
                    group_field="moda",
                    group=moda,
                    message=(
                        f"Housekeeping: {actor_description} "
                        f"withdrew {voter_name}'s vote to expel "
                        f"{candidate_name}. "
                        f"Current tally: {remaining_votes} "
                        f"of {majority_required} votes required."
                    ),
                )

            vote = serializers.UserSerializer(voter)

            return {
                "status": "success",
                "action": "undo_vote_out",
                "message": "vote removed successfully.",
                "user": vote.data,
                "instance": serialized_data,
            }
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"undo_vote_out", "message": "Could not remove vote.","user":vote.data}

    @database_sync_to_async
    def put_forward(self, data):
        """ change the circle gelegation."""
        try:
            voter = User.objects.get(username=data["voter"])
            moda = models.ModaModel.objects.get(
                code=self.moda_name,
            )
            member = models.ModaMembers.objects.get(
                pk=data["member"],
                moda=moda,
                is_member=True,
            )

            actor = self.scope["user"]

            actor_membership = models.ModaMembers.objects.filter(
                user=actor,
                moda=moda,
                is_member=True,
            ).first()

            voter_is_member = models.ModaMembers.objects.filter(
                user=voter,
                moda=moda,
                is_member=True,
            ).exists()

            if (
                actor_membership is None
                or not voter_is_member
                or (
                    actor.pk != voter.pk
                    and not actor_membership.is_delegate
                )
            ):
                return {
                    "status": "error",
                    "action": "put_forward",
                    "message": "Not authorized to cast this replacement vote.",
                    "user": serializers.UserSerializer(actor).data,
                }
            with transaction.atomic():
                total_members = models.ModaMembers.objects.filter(
                    moda=moda,
                    is_member=True,
                ).count()

                majority_required = total_members // 2 + 1

                instance, created = (
                    models.PutFarwardModaMember.objects.get_or_create(
                        voter=voter,
                        candidate=member,
                        moda=moda,
                        defaults={"agent": actor},
                    )
                )

                if created:
                    current_votes = (
                        models.PutFarwardModaMember.objects.filter(
                            moda=moda,
                            candidate=member,
                        ).count()
                    )

                    actor_name = user_display_name(actor)
                    voter_name = user_display_name(voter)
                    candidate_name = user_display_name(member.user)

                    if actor.pk == voter.pk:
                        actor_description = actor_name
                    else:
                        actor_description = (
                            f"{actor_name}, acting as "
                            f"{voter_name}'s agent,"
                        )

                    post_succession_update(
                        message_model=models.ModaBackNForthChat,
                        group_field="moda",
                        group=moda,
                        message=(
                            f"Housekeeping: {actor_description} "
                            f"voted to make {candidate_name} "
                            f"the Caucus Delegate. "
                            f"Current tally: {current_votes} "
                            f"of {majority_required} votes required."
                        ),
                    )

            serialized = serializers.PutFarwardModaMemberSerializer(
                instance
            )
            vote = serializers.UserSerializer(voter)

            return {
                "status": "success",
                "action": "put_forward",
                "message": "voted for delegate.",
                "user": vote.data,
                "instance": serialized.data,
            }
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"put_forward", "message": "Could not vote for delegate.","user":vote.data}
        
    @database_sync_to_async
    def undo_put_forward(self, data):
        actor = self.scope.get("user")

        if actor is None or not actor.is_authenticated:
            return {
                "status": "error",
                "action": "undo_put_forward",
                "message": "Authentication required.",
            }

        try:
            with transaction.atomic():
                moda = models.ModaModel.objects.select_for_update().get(
                    code=self.moda_name,
                )
                voter = User.objects.get(
                    username=data["voter"],
                )
                member = models.ModaMembers.objects.get(
                    pk=data["member"],
                    moda=moda,
                    is_member=True,
                )

                actor_membership = models.ModaMembers.objects.filter(
                    user=actor,
                    moda=moda,
                    is_member=True,
                ).first()

                voter_is_member = models.ModaMembers.objects.filter(
                    user=voter,
                    moda=moda,
                    is_member=True,
                ).exists()

                if (
                    actor_membership is None
                    or not voter_is_member
                    or (
                        actor.pk != voter.pk
                        and not actor_membership.is_delegate
                    )
                ):
                    return {
                        "status": "error",
                        "action": "undo_put_forward",
                        "message": "Not authorized to withdraw this vote.",
                    }

                instance = models.PutFarwardModaMember.objects.get(
                    voter=voter,
                    candidate=member,
                    moda=moda,
                )

                serialized_data = (
                    serializers.PutFarwardModaMemberSerializer(instance).data
                )

                instance.delete()

                remaining_votes = models.PutFarwardModaMember.objects.filter(
                    candidate=member,
                    moda=moda,
                ).count()

                total_members = models.ModaMembers.objects.filter(
                    moda=moda,
                    is_member=True,
                ).count()

                majority_required = total_members // 2 + 1

                actor_name = user_display_name(actor)
                voter_name = user_display_name(voter)
                candidate_name = user_display_name(member.user)

                if actor.pk == voter.pk:
                    actor_description = actor_name
                else:
                    actor_description = (
                        f"{actor_name}, acting as "
                        f"{voter_name}'s agent,"
                    )

                post_succession_update(
                    message_model=models.ModaBackNForthChat,
                    group_field="moda",
                    group=moda,
                    message=(
                        f"Housekeeping: {actor_description} "
                        f"withdrew {voter_name}'s vote to make "
                        f"{candidate_name} the Caucus Delegate. "
                        f"Current tally: {remaining_votes} "
                        f"of {majority_required} votes required."
                    ),
                )

            return {
                "status": "success",
                "action": "undo_put_forward",
                "message": "Replacement vote withdrawn.",
                "user": serializers.UserSerializer(voter).data,
                "instance": serialized_data,
            }

        except (
            KeyError,
            User.DoesNotExist,
            models.ModaModel.DoesNotExist,
            models.ModaMembers.DoesNotExist,
            models.PutFarwardModaMember.DoesNotExist,
        ):
            return {
                "status": "error",
                "action": "undo_put_forward",
                "message": "Could not withdraw replacement vote.",
            }

    @database_sync_to_async
    def invitation_key(self):
        try:
            moda = models.ModaModel.objects.get(code=self.moda_name)
            moda.invitation_key = models.generate_unique_invitation_key()
            moda.save()
            serialized = serializers.ModaSerializer(moda)
            return {"status":"success","action":'invitation_key', "message":"invitation key generated successfully.", "moda":serialized.data}
        except:
            return {"status": "error","action":"invitation_key", "message": "Could note generate invitation key."}
    
    @database_sync_to_async
    def voteIn(self,data):  
        try:
            voter = User.objects.get(username=data["voter"])
            moda = models.ModaModel.objects.get(
                code=self.moda_name,
            )
            candidate = models.ModaMembers.objects.get(
                pk=data["candidate"],
                moda=moda,
                is_member=False,
            )

            actor = self.scope["user"]

            actor_membership = models.ModaMembers.objects.filter(
                user=actor,
                moda=moda,
                is_member=True,
            ).first()

            voter_is_member = models.ModaMembers.objects.filter(
                user=voter,
                moda=moda,
                is_member=True,
            ).exists()

            if (
                actor_membership is None
                or not voter_is_member
                or (
                    actor.pk != voter.pk
                    and not actor_membership.is_delegate
                )
            ):
                return {
                    "status": "error",
                    "action": "vote_in",
                    "message": "Not authorized to cast this admission vote.",
                    "user": serializers.UserSerializer(actor).data,
                }
            with transaction.atomic():
                total_members = models.ModaMembers.objects.filter(
                    moda=moda,
                    is_member=True,
                ).count()

                majority_required = total_members // 2 + 1

                instance, created = (
                    models.VoteInModaMember.objects.get_or_create(
                        voter=voter,
                        moda=moda,
                        candidate=candidate,
                        defaults={"agent": actor},
                    )
                )

                if created:
                    current_votes = models.VoteInModaMember.objects.filter(
                        moda=moda,
                        candidate=candidate,
                    ).count()

                    actor_name = user_display_name(actor)
                    voter_name = user_display_name(voter)
                    candidate_name = user_display_name(candidate.user)

                    if actor.pk == voter.pk:
                        actor_description = actor_name
                    else:
                        actor_description = (
                            f"{actor_name}, acting as "
                            f"{voter_name}'s agent,"
                        )

                    post_succession_update(
                        message_model=models.ModaBackNForthChat,
                        group_field="moda",
                        group=moda,
                        message=(
                            f"Housekeeping: {actor_description} "
                            f"voted to admit {candidate_name}. "
                            f"Current tally: {current_votes} "
                            f"of {majority_required} votes required."
                        ),
                    )

                    candidate.refresh_from_db()

                    if candidate.is_member:
                        post_succession_update(
                            message_model=models.ModaBackNForthChat,
                            group_field="moda",
                            group=moda,
                            message=(
                                f"Housekeeping: {candidate_name} "
                                f"was admitted to the Second Link "
                                f"after receiving the required majority."
                            ),
                        )

            serialized = serializers.VoteInModaMemberSerializer(instance)
            vote = serializers.UserSerializer(voter)

            return {
                "status": "success",
                "action": "vote_in",
                "message": "voted successfully.",
                "user": vote.data,
                "instance": serialized.data,
            }
        except:
            vote = serializers.UserSerializer(voter)
            return {"status": "error","action":"vote_in", "message": "Could not vote.","user":vote.data}
    
    
    @database_sync_to_async
    def undo_vote_in(self, data):
        actor = self.scope.get("user")

        if actor is None or not actor.is_authenticated:
            return {
                "status": "error",
                "action": "undo_vote_in",
                "message": "Authentication required.",
            }

        try:
            with transaction.atomic():
                moda = models.ModaModel.objects.get(
                    code=self.moda_name,
                )
                voter = User.objects.get(
                    username=data["voter"],
                )
                candidate = models.ModaMembers.objects.get(
                    pk=data["candidate"],
                    moda=moda,
                    is_member=False,
                )

                actor_membership = models.ModaMembers.objects.filter(
                    user=actor,
                    moda=moda,
                    is_member=True,
                ).first()

                voter_is_member = models.ModaMembers.objects.filter(
                    user=voter,
                    moda=moda,
                    is_member=True,
                ).exists()

                if (
                    actor_membership is None
                    or not voter_is_member
                    or (
                        actor.pk != voter.pk
                        and not actor_membership.is_delegate
                    )
                ):
                    return {
                        "status": "error",
                        "action": "undo_vote_in",
                        "message": "Not authorized to withdraw this vote.",
                    }

                instance = models.VoteInModaMember.objects.get(
                    voter=voter,
                    candidate=candidate,
                    moda=moda,
                )

                serialized_data = (
                    serializers.VoteInModaMemberSerializer(instance).data
                )

                instance.delete()

                remaining_votes = models.VoteInModaMember.objects.filter(
                    candidate=candidate,
                    moda=moda,
                ).count()

                total_members = models.ModaMembers.objects.filter(
                    moda=moda,
                    is_member=True,
                ).count()

                majority_required = total_members // 2 + 1

                actor_name = user_display_name(actor)
                voter_name = user_display_name(voter)
                candidate_name = user_display_name(candidate.user)

                if actor.pk == voter.pk:
                    actor_description = actor_name
                else:
                    actor_description = (
                        f"{actor_name}, acting as "
                        f"{voter_name}'s agent,"
                    )

                post_succession_update(
                    message_model=models.ModaBackNForthChat,
                    group_field="moda",
                    group=moda,
                    message=(
                        f"Housekeeping: {actor_description} "
                        f"withdrew {voter_name}'s vote to admit "
                        f"{candidate_name}. "
                        f"Current tally: {remaining_votes} "
                        f"of {majority_required} votes required."
                    ),
                )

            return {
                "status": "success",
                "action": "undo_vote_in",
                "message": "Admission vote withdrawn.",
                "user": serializers.UserSerializer(voter).data,
                "instance": serialized_data,
            }

        except (
            KeyError,
            User.DoesNotExist,
            models.ModaModel.DoesNotExist,
            models.ModaMembers.DoesNotExist,
            models.VoteInModaMember.DoesNotExist,
        ):
            return {
                "status": "error",
                "action": "undo_vote_in",
                "message": "Could not withdraw admission vote.",
            }
    @database_sync_to_async
    def remove_candidate(self, data):
        """ remove the candidate or members from this circle
        """
        try:
            remover = self.scope["user"]
            moda = models.ModaModel.objects.get(
                code=self.moda_name,
            )

            is_delegate = models.ModaMembers.objects.filter(
                user=remover,
                moda=moda,
                is_member=True,
                is_delegate=True,
            ).exists()

            if not is_delegate:
                return {
                    "status": "error",
                    "action": "remove_candidate",
                    "message": (
                        "Only the current Caucus Delegate may "
                        "remove another member."
                    ),
                    "user": serializers.UserSerializer(remover).data,
                }

            member = models.ModaMembers.objects.get(
                pk=data["candidate"],
                moda=moda,
            )
            remove_second_link_member_as_delegate(
                moda=moda,
                actor=remover,
                membership_pk=member.pk,
            )
            vote = serializers.UserSerializer(remover)
            return {"status":"success","action":'remove_candidate', "message":"removed successfully.", "user":vote.data}
        except:
            # vote = serializers.UserSerializer(remover)
            return {"status": "error","action":"remove_candidate", "message": "Could note remove candidate.","user":""}

    @database_sync_to_async
    def DissolveSecDel(self, payload):
        with transaction.atomic():
            moda = models.ModaModel.objects.select_for_update().get(
                code=self.moda_name
            )

            actor = self.scope["user"]

            membership = models.ModaMembers.objects.filter(
                pk=payload.get("member"),
                user=actor,
                moda=moda,
                is_member=True,
                is_delegate=True,
            ).first()

            if membership is None:
                return {
                    "status": "error",
                    "action": "dissolve",
                    "message": (
                        "Only the current Caucus Delegate "
                        "may dissolve this Second Link."
                    ),
                }

            accepted_count = models.ModaMembers.objects.filter(
                moda=moda,
                is_member=True,
            ).count()

            if accepted_count != 1:
                return {
                    "status": "error",
                    "action": "dissolve",
                    "message": (
                        "The Second Link cannot be dissolved "
                        "while other accepted members remain."
                    ),
                }

            moda.delete()

            return {
                "status": "success",
                "action": "dissolve",
                "message": "Second Link dissolved.",
            }

    async def receive(self, text_data):
        """ Check messages. If message is for voting in a candidate then vote the candidate. """
        data = json.loads(text_data)

        match data["action"]:
            case 'remove_candidate':
                # remove the candidate or member and return the circle members
                res = await self.remove_candidate(data)
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return
            case 'vote_in':
                # vote in the candidate and return the circle members
                res = await self.voteIn(data["payload"])
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return
            case "undo_vote_in":
                res = await self.undo_vote_in(data["payload"])

                if res["status"] == "error":
                    await self.channel_layer.group_send(
                        self.room_name,
                        {
                            "type": "send_members",
                            "members_list": res,
                        },
                    )
                else:
                    await self.channel_layer.group_send(
                        self.room_name,
                        {
                            "type": "send_members",
                            "members_list": {
                                "status": "success",
                                "action": res,
                                "member_list": await self.get_members(),
                            },
                        },
                    )
                return
            case "putForward":
                res = await self.put_forward(data["payload"])
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return
            
            case "undo_putForward":
                res = await self.undo_put_forward(data["payload"])
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return
            
            case "vote_out":
                 # vote in the candidate and return the circle members
                res = await self.member_vote_out(data["payload"])
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return
            
            case "undo_vote_out":
                 # vote in the candidate and return the circle members
                res = await self.undo_vote_out(data["payload"])
                if res['status'] == 'error':
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': res,
                        }
                    )
                else:
                    await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list':{'status':"success",'action': res ,'member_list': await self.get_members()} ,
                        }
                    )
                return

            case "join":
                await self.channel_layer.group_send(self.room_name, {
                    'type': 'send_members',
                    'members_list':{'status':"success", 'action':'member_listing', 'member_list': await self.get_members()} ,
                    }
                )
                return
            
            case "invitationKey":
                sd = await self.invitation_key()
                await self.channel_layer.group_send(self.room_name, {
                        'type': 'send_members',
                        'members_list': {"status": "success","action":'invitationKey', "moda":sd['moda'], 'member_list': await self.get_members()}
                        }
                    )
                return
           
            case "dissolve":
                obj = await self.DissolveSecDel(data["payload"])

                if obj["status"] == "success":
                    await self.channel_layer.group_send(
                        self.room_name,
                        {
                            "type": "send_members",
                            "members_list": {
                                "status": "success",
                                "action": "dissolve",
                            },
                        },
                    )
                else:
                    await self.send(text_data=json.dumps(obj))

                return

    # Send to each member
    async def send_members(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event['members_list']))
