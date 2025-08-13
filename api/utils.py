"""
Utility functions for the API app
"""
import random
from django.contrib.auth.models import User


def entry_code_generator():
    """
    this is the entry code generator.
    It uses random and checks for the database.
    return the code if it's not taken
    """
    code = str(random.choice('abcdefghijklmnpqrstuvwxyz'))
    code += str(random.randint(1, 9))
    code += str(random.choice('abcdefghijklmnpqrstuvwxyz'))
    code += str(random.randint(1, 9))
    code += str(random.choice('abcdefghijklmnpqrstuvwxyz'))
    code = code.upper()
    is_exist = User.objects.filter(username=code).exists()

    if is_exist:
        return entry_code_generator()
    return code
