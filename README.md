# Democracy Straight-Up Project
This repo is a prototype of the Democracy Straight-Up Project.

1. To get started, click the 'Claim Your Seat' button on Homepage, fill in the information required and register
2. After registration, you can 'Enter The Floor' and
    - Create a CrCl
    - Join a CrCl
    - Manage rooms
    - Vote on bills

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
1. Make a directory anywhere in your machine.
2. Inside the directory, create python virtualenv and activate it.
3. Clone this repo inside the directory.
4. Make sure MySQL client and sarver are installed on your local machine.
5. Install all the requirements inside the `requirements.txt` file.
    - for installing the packages; user `pip install -r requirements.txt`
6. Then simply apply the migrations:

    `python3 manage.py migrate`
    

   You can now run the development server:

    `python3 manage.py runserver`
   
   By default it will run on local host  http://127.0.0.1:8000

7. To load data into district tables, run the loaddata command for fixture 
   `python3 manage.py loaddata districts_data.json`

8. Setup the env file to set config variables. 
    - email config
    - database 
        - DSU uses db.sqlite file database for production

## API

### Retrieve Entry Code

- URL: /get-username/
- Method: `POST`
- Authentication Required: No
- Permissions Required: No
- Parameters:

  | Name | Type | Description | Required |
  | --- | ----------- | ----------- | ----------- |
  | email | String | User's email | Yes|

- Example request:

```json
{
  "email": "user@example.com",
}
```

- Response:
  200 OK

- Email:

```
Hi {{name}},
Your entry code is: T4N9L
Please use this code to enter the floor.
```


- Error Response:
400 Bad Request
```json
{
    "non_field_errors": [
        "User with given email does not exist"
    ]
}
```


