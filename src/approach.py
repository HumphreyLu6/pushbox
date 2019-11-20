import rospy
import smach, smach_ros
import actionlib
import tf
from ar_track_alvar_msgs.msg import AlvarMarker, AlvarMarkers
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from geometry_msgs.msg import Twist, Point, Quaternion

import utils

class SearchParkTag(smach.State):
    def __init__(self):
        smach.State.__init__(self,
                             outcomes = ['end', 'found'])
        self.ar_tag_id = None

    def execute(self, userdata):
        self.ar_pose_marker_sub = rospy.Subscriber("/ar_pose_marker", AlvarMarkers, self.ar_tag_callback)
        rospy.wait_for_message("/ar_pose_marker", AlvarMarkers)
        while not rospy.is_shutdown():
            if self.ar_tag_id != None:
                self.ar_pose_marker_sub.unregister()

                self.transformer = utils.Transformer()
                self.transformer.build_new_frame('ar_tag_'+ str(self.ar_tag_id), 'park_pose',
                                                 (0, 0, 0.4), (0, 0, 1, 0)
                                                )
                rospy.sleep(0.1)
                return 'found'

        self.ar_pose_marker_sub.unregister()
        return 'end'
                

    def ar_tag_callback(self, msg):
        if self.ar_tag_id == None and len(msg.markers) != 0:
            self.ar_tag_id = msg.markers[0].id
            
class SearchBox(smach.State):
    def __init__(self):
        smach.State.__init__(self, 
                            outcomes=['end', 'found'])
        
        self.ar_tag_id = None

    def execute(self, userdata):
        self.ar_pose_marker_sub = rospy.Subscriber("/ar_pose_marker", AlvarMarkers, self.ar_tag_callback)
        rospy.wait_for_message("/ar_pose_marker", AlvarMarkers)
        while not rospy.is_shutdown():
            if self.ar_tag_id != None:
                self.ar_pose_marker_sub.unregister()

                self.transformer = utils.Transformer()

                box_edge_length = 0.334
                distance_to_box_center = 0.5

                tag_box_transition = (0, 0, box_edge_length/2)
                tag_box_rotation = (0, 0, 1, 0)
                self.transformer.build_new_frame('ar_tag_'+ str(self.ar_tag_id), 'box_center_pose',
                                                tag_box_transition, tag_box_rotation
                                                )

                self.transformer.build_new_frame('box_center_pose', 'box_front_park', 
                                                (0, 0, distance_to_box_center), (0, 0, 0, 1)
                                                ) #(0, 0, 0)
                self.transformer.build_new_frame('box_center_pose', 'box_back_park',
                                                (0, 0, - distance_to_box_center), (0, 0, 1, 0)
                                                ) #(0, 0, 180)
                self.transformer.build_new_frame('box_center_pose', 'box_left_park',
                                                (0, - distance_to_box_center, 0), (0, 0, 0.707, 0.707)
                                                ) #(0, 0, 90)
                self.transformer.build_new_frame('box_center_pose', 'box_right_park', 
                                                (0, distance_to_box_center, 0), (0, 0, -0.707, 0.707)
                                                ) #(0, 0, 90)
                rospy.sleep(0.2)
                return 'found'
        self.ar_pose_marker_sub.unregister()
        return 'end'

    def ar_tag_callback(self, msg):
        if self.ar_tag_id == None and len(msg.markers) != 0:
            self.ar_tag_id = msg.markers[0].id

class Approach(smach.State):
    def __init__(self):
        smach.State.__init__(self, 
                            outcomes = ['end', 'failed', 'arrived'])
        self.client = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        self.client.wait_for_server()

    def execute(self, userdata):

        if rospy.is_shutdown():
            return 'end'

        goal = utils.goal_pose('box_back_park')
        self.client.send_goal(goal)
        result = self.client.wait_for_result(rospy.Duration.from_sec(0))
        
        if result == False:
            return 'failed'
        return 'arrived'   

class Push(smach.State):
    def __init__(self):
        smach.State.__init__(self, 
                            outcomes = ['end', 'completed'])
    
    def execute(self, userdata):
        self.transformer = utils.Transformer()
        tans, _ = self.transformer.look_up_transform('park_pose', 'box_center_pose')
        while not rospy.is_shutdown():
            print(tans)
        return 'end'

if __name__ == "__main__":

    rospy.init_node("approach")
    
    approach_sm = smach.StateMachine(
                    outcomes = ['end', 'completed', 'failed'])

    with approach_sm:
        smach.StateMachine.add('SearchParkTag', SearchBox(),
                                transitions = { 'end':'end',
                                                'found':'SearchBox'})

        smach.StateMachine.add('SearchBox', SearchBox(),
                                transitions = { 'end':'end',
                                                'found':'Approach'})

        smach.StateMachine.add('Approach', Approach(),
                                transitions = { 'end':'end',
                                                'failed':'failed',
                                                'arrived':'completed'})

        smach.StateMachine.add('Push', Push(),
                                transitions = { 'end':'end',
                                                'completed':'completed'})
    
    outcome = approach_sm.execute()
    rospy.spin()
