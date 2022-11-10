from typing import List


class IntegrationEvent:

    def __init__(self, event_name:str, event_type:str, message:List[str]=[]) -> None:
        self.event_name = event_name
        self.event_type = event_type
        self.message = message
    
    def to_json(self):
        #return json.dumps(self.message)
        pass