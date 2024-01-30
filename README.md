# Democracy Straight-Up Project

This repo is a prototype of the Democracy Straight-Up Project.

1. to get started, click the 'Claim Your Seat' button on Homepage, fill in the information required and register
2. after registration, you can 'Enter The Floor' and
   - create a Pod
   - join a Pod
   - manage rooms
   - vote on bills

## Structure

```
{{ Claim-Your-Seat }}/
|---Procfile <-- tells Heroku how it should start up the project.
|---api/
|   |-- migrations/
|   |-- templates/
│   |--- __init__.py
|   |-- admin.py
|   |-- apps.py
|   |-- models.py
|   |-- views.py
|   |-- urls.py
|   |-- serializers.py
|   |-- tests.py
|---dsu/
│   |--- asgi.py <-- ASGI config for dsu project.
│   |--- __init__.py
│   |--- settings.py <-- Django settings for dsu project.
│   |--- urls.py
│   |--- wsgi.py <-- WSGI config for dsu project.
|-- live/
|   |-- migrations/
|   |-- templates/
│   |--- __init__.py
|   |-- admin.py
|   |-- apps.py
|   |-- models.py
|   |-- views.py
|   |-- urls.py
|   |-- consumers.py
|   |-- tests.py
|   |-- podBackNForthConsumers.py
|   |-- routing.py
|---vote/
|   |-- migrations/
|   |-- templates/
|   |-- static/
|   |-- fixtures/
│   |--- __init__.py
|   |-- admin.py
|   |-- apps.py
|   |-- forms.py
|   |-- models.py
|   |-- signals.py
|   |-- token.py
|   |-- views.py
|   |-- urls.py
|   |-- tests.py
|---manage.py
|---requirements.txt <-- all required packages for the project to work.
```

### how to set up the project on you local machine:

1. make a directory anywhere in your machine.
2. inside the directory, create python virtualenv and activate it.
3. clone this repo inside the directory.
4. make sure MySQL client and surver are installed on your local machine.
5. install all the requirements inside the `requirements.txt` file.
   - for installing the packages; user `pip install -r requirements.txt`
6. Then simply apply the migrations:

   `python3 manage.py migrate`

   You can now run the development server:

   `python3 manage.py runserver`

   By default it will run on local host http://127.0.0.1:8000

7. to load data into district tables, run the loaddata command for fixture
   `python3 manage.py loaddata districts_data.json`

8. setup the env file to set config variables.
   - email config
   - database
     - DSU uses db.sqlite file database for production

## API

### Password Reset Request

- URL: `/api/reset-password/`
- Method: `POST`
- Parameters:
  | Name | Type | Description | Required |
  | --- | ----------- | ----------- | ----------- |
  | email | String | User email | Yes|

- Example request:

```json
{
  "email": "test@test.com"
}
```

- Response:
  200 OK

```json
{
  "message": "Email sent."
}
```

- Email response:
```
Hi XXX,
Please click on the link to reset your password,
https://http://{url}/api/activate/{uidb64}/{token}
```

### Password Reset Confirm

- URL: `/api/reset-password-confirm/`
- Method: `POST`
- Parameters:
  | Name | Type | Description | Required |
  | --- | ----------- | ----------- | ----------- |
  | uidb64 | String (base64) | user id | Yes|
  | token | String | user token from email | Yes|
  | new_password | String | new_password | Yes|
  | new_password2 | String | new_password | Yes|

- Example request:

```json
{
  "uidb64": "Ma",
  "token": "c1m74w-cc037873fec6bc23274xxxxcac0e98f",
  "new_password": "123456",
  "new_password2": "123456"
}
```

- Response:
  200 OK

```json
{
    "message": "Password is reset"
}
```

- Error Response:
400 Bad Request
```json
{
    "new_password2": [
        "Password fields didn't match."
    ]
}
```
