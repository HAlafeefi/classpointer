import json
import requests
import uuid
from contextlib import closing
from websocket import create_connection

class ClassPointer:
    CLASSPOINT_API = "https://apitwo.classpoint.app/classcode/region/byclasscode?classcode={CLASSCODE}"
    PARTICIPANTS_API = "https://{cpcs_region}.classpoint.app/liveclasses/saved-participants?email={presenter_email}"
    VALIDATE_API = 'https://{cpcs_region}.classpoint.app/liveclasses/validate-join'
    WEBSOCKET_URL = "wss://{cpcs_region}.classpoint.app/classsession"
    PRESENTER_API = 'https://api.classpoint.app/users/dto/presenter-app?email={presenter_email}'
    STARS_API = 'https://apitwo.classpoint.app/savedclasses/participant/adjust-points?savedClassId={savedClassId}&participantId={participantId}&pointsDelta={stars}'
    AUTHORIZATION = ('Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6InNodW1haWQzNjBAZ21haWwuY29tIiwidXNlcklkI'
                     'joiNjYyZWIwZWYwOTExMGY5ZjQyNjYwYTAzIiwiaWF0IjoxNzE0MzM1OTgzLCJleHAiOjE3MTU1NDU1ODN9.XlTbwt3qFscyR'
                     'TtFMe7OAbTB7COBvRjOO-pEhTFcxrY')

    def __init__(self, classcode: str = "AY11", user_name: str = "Hamad 1096682"):
        self.classcode = classcode.upper()
        self.user_name = user_name
        self.participant_id = f"participant-{uuid.uuid4()}"

        self.presenter_email = None
        self.cpcs_region = None
        self.classSessionId = None
        self.savedClassId = None
        self.participantIdn = None

        self.fetch_presenter_info()
        self.check_participant()
        self.validate_request()

    def fetch_presenter_info(self):
        # Fetch presenter's email and region
        presenter_info = self._get_api_response("CLASSPOINT_API", {'CLASSCODE': self.classcode})
        self.presenter_email = presenter_info['presenterEmail']
        self.cpcs_region = presenter_info['cpcsRegion']

    def check_participant(self):
        # Ensure user with USER_NAME exists
        participants = self._get_api_response("PARTICIPANTS_API", {'cpcs_region': self.cpcs_region, 'presenter_email': self.presenter_email})
        usernames = [user["participantUsername"] for user in participants]
        if self.user_name not in usernames:
            raise Exception("No user with such name")

    def validate_request(self):
        # Validate user join
        payload = {
            'presenterEmail': self.presenter_email,
            'classCode': self.classcode,
            'participantId': self.participant_id,
            'participantUsername': self.user_name
        }
        self._post_api_request("VALIDATE_API", payload)

    def websocketer(self, quiz: bool = True):
        with closing(create_connection(self._get_api_url("WEBSOCKET_URL"))) as conn:
            # Initialization
            conn.send('{"protocol":"json","version":1}')

            # Send participant startup message
            startup_message = self._create_startup_message()
            conn.send(json.dumps(startup_message) + '')

            conn.recv()
            message = conn.recv()

            messages = str(message).split('')
            for mess in messages:
                try:
                    mess = json.loads(mess)
                except json.decoder.JSONDecodeError:
                    break

                if len(mess) > 0 and "target" in mess and mess["target"] == "SendJoinClass":
                    arguments = mess["arguments"][0]
                    self.classSessionId = arguments['classSessionId']
                    self.participantIdn = arguments['participantId']

                    if quiz:
                        if arguments['activityModel']:
                            activity = arguments['activityModel']
                            print("QUIZ ON")

                            return [True, activity['mcChoices'], activity['mcIsAllowSelectMultiple'],
                                    activity["mcCorrectAnswers"], activity['yourSubmittedResponses']]

                        else:
                            print('QUIZ OFF')
                            return [False]

    def _get_api_response(self, api_key, params=None):
        api_url = self._get_api_url(api_key).format(**params) if params else self._get_api_url(api_key)
        response = requests.get(api_url)
        response_json = response.json()

        try:
            response.raise_for_status()
        except requests.HTTPError:
            raise requests.HTTPError(response_json['message'])


        return response_json

    def _post_api_request(self, api_key, payload):
        api_url = self._get_api_url(api_key)
        response = requests.post(api_url, params=payload)
        response.raise_for_status()

    def _get_api_url(self, api_key):
        return getattr(self, api_key).format(cpcs_region=self.cpcs_region, presenter_email=self.presenter_email, CLASSCODE=self.classcode)

    def _create_startup_message(self):
        participant_data = {
            "participantUsername": self.user_name,
            "participantName": self.user_name,
            "participantId": self.participant_id,
            "cpcsRegion": self.cpcs_region,
            "presenterEmail": self.presenter_email,
            "classSessionId": ""
        }
        return {
            "arguments": [participant_data],
            "invocationId": "0",
            "target": "ParticipantStartup",
            "type": 1
        }

    def add_stars(self, stars: int):
        presenter_info = self._get_api_response("PRESENTER_API")
        savedclasses = presenter_info["userProfile"]["savedClasses"]

        for clas in savedclasses:
            if clas['savedClassCode'] == self.classcode:
                self.savedClassId = clas['savedClassId']

        if not self.participantIdn:
            self.websocketer(quiz=False)

        payload = {
            "savedClassId": self.savedClassId,
            "participantId": self.participantIdn,
            "stars": str(stars)
        }
        self._post_api_request("STARS_API", payload)

if __name__ == "__main__":
    sus = ClassPointer(classcode="ay11").websocketer()
    print(sus)
