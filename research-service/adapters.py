"""Three deliberately different software-controller command interfaces.
These are test interfaces, not implementations of NTCIP or a vendor protocol.
"""
class ControllerAdapter:
    def __init__(self,profile):self.profile=profile
    def encode(self,action):
        if action not in ['GREEN','RED']:raise ValueError('Unsupported movement action')
        if self.profile=='Limited adapter':
            return {'operation':'select_program','program':'priority' if action=='GREEN' else 'clearance'}
        if self.profile=='Gateway adapter':
            return {'operation':'gateway_permission','allow_movement':action=='GREEN'}
        return {'operation':'phase_hold','state':action}
    def decode(self,command):
        for action in ['GREEN','RED']:
            if command==self.encode(action):return action
        raise ValueError('Native command incompatible with controller profile')
    def operations(self):return [self.encode(a)['operation'] for a in ['GREEN','RED']]
