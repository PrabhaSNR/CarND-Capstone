#!/usr/bin/env python

import rospy
from geometry_msgs.msg import PoseStamped
from styx_msgs.msg import Lane, Waypoint
from std_msgs.msg import Int32

from scipy.spatial import KDTree
import numpy as np
import math

'''
This node will publish waypoints from the car's current position to some `x` distance ahead.

As mentioned in the doc, you should ideally first implement a version which does not care
about traffic lights or obstacles.

Once you have created dbw_node, you will update this node to use the status of traffic lights too.

Please note that our simulator also provides the exact location of traffic lights and their
current status in `/vehicle/traffic_lights` message. You can use this message to build this node
as well as to verify your TL classifier.

TODO (for Yousuf and Aaron): Stopline location for each traffic light.
For viewing the log file when roscore is running.
roscd log

or 

Update launch file with output="screen"/ to view logs
'''

PUB_FREQUENCY = 10 # Gives control over the publishing frequency
LOOKAHEAD_WPS = 50 # Number of waypoints we will publish. You can change this number
MAX_DECEL = 0.5     # Maximum deceleration


class WaypointUpdater(object):
    def __init__(self):
        rospy.init_node('waypoint_updater')

        rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb, queue_size=2)
        rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb, queue_size=8)

        # TODO: Add a subscriber for /traffic_waypoint and /obstacle_waypoint below
        rospy.Subscriber('/traffic_waypoint', Int32, self.traffic_cb)
        #rospy.Subscriber('/obstacle_waypoint', Int32, self.obstacle_cb, queue_size=1)

        self.final_waypoints_pub = rospy.Publisher('final_waypoints', Lane, queue_size=1)

        # TODO: Add other member variables you need below
        self.base_lane = None
        self.pose = None
        self.waypoints_2d = None
        self.waypoint_tree = None
        self.stopline_wp_idx = -1
        #rospy.spin()
        self.decelerate_count = 0

        self.loop()
        
    # Infinite loop
    def loop(self):
        rate = rospy.Rate(PUB_FREQUENCY)
        while not rospy.is_shutdown():
                self.publish_waypoints()
            rate.sleep()

    def pose_cb(self, msg):
        # TODO: Implement
        self.pose = msg
        #rospy.logwarn("Pose")

    def waypoints_cb(self, waypoints):
        # TODO: Implement
        self.base_lane = waypoints
        #rospy.logwarn("Waypoints in Baselane")
        if not self.waypoints_2d:
            self.waypoints_2d = [[waypoint.pose.pose.position.x, waypoint.pose.pose.position.y] for waypoint in waypoints.waypoints]
            #rospy.logwarn("Waypoints in waypoint treed{}".format(self.waypoints_2d))
            self.waypoint_tree = KDTree(self.waypoints_2d)
            #rospy.logwarn("Waypoints in waypoint tree")

    def traffic_cb(self, msg):
        # TODO: Callback for /traffic_waypoint message. Implement
        #if self.stopline_wp_idx != msg.data:
        rospy.logwarn("LIGHT: new stopline_wp_idx={}, old stopline_wp_idx={}".format(msg.data, self.stopline_wp_idx))
        self.stopline_wp_idx = msg.data

    def obstacle_cb(self, msg):
        # TODO: Callback for /obstacle_waypoint message. We will implement it later
        # I am not using it in this project
        pass
        
    # Get the closest waypoint index
    def get_closest_waypoint_idx(self):
        # Current pose (x,y) and index
        x = self.pose.pose.position.x
        y = self.pose.pose.position.y
        closest_idx = self.waypoint_tree.query([x,y], 1)[1]

        # Check if point is ahead or behind the car
        closest_coord = self.waypoints_2d[closest_idx]
        prev_coord = self.waypoints_2d[closest_idx-1]
        
        # Equation for hyperplane through closest_coords
        cl_vect = np.array(closest_coord)
        prev_vect = np.array(prev_coord)
        pos_vect = np.array([x,y])

        val = np.dot(cl_vect-prev_vect, pos_vect-cl_vect)
        if val > 0:
            closest_idx = (closest_idx+1) % len(self.waypoints_2d)

        return closest_idx

    # Publishes the final lane
    def publish_waypoints(self):
        final_lane = self.generate_lane()
        self.final_waypoints_pub.publish(final_lane)

    def generate_lane(self):
        lane = Lane()
        # Get the closest and farthest index
        closest_idx = self.get_closest_waypoint_idx()
        farthest_idx = closest_idx + LOOKAHEAD_WPS
        base_waypoints = self.base_lane.waypoints[closest_idx:farthest_idx]
        rospy.logwarn("closest index :{}  and stopline index:{}".format(closest_idx, self.stopline_wp_idx))
        # If no traffic light was detected, publish the base_waypoints as it is
        if (self.stopline_wp_idx== -1) or (self.stopline_wp_idx >= farthest_idx):
            lane.waypoints = base_waypoints
            rospy.logwarn("No Change")
        else:
            rospy.logwarn("Reduce speed")
            lane.waypoints = self.decelerate_waypoints(base_waypoints, closest_idx)

        return lane
        
    def decelerate_waypoints(self, waypoints, closest_idx):
        temp = []
        for i, wp in enumerate(waypoints):
            p = Waypoint()
            p.pose = wp.pose
            stop_idx = max(self.stopline_wp_idx - closest_idx - 2, 0)            
            dist = self.distance(waypoints, i, stop_idx)            
            vel = math.sqrt(2 * MAX_DECEL * dist)
            if vel < 1.:
                vel = 0

            p.twist.twist.linear.x = min(vel, wp.twist.twist.linear.x)
            temp.append(p)

        self.decelerate_count += 1
        if (self.decelerate_count % 5) == 0:
            size = len(waypoints) - 1
            vel_start = temp[0].twist.twist.linear.x
            vel_end = temp[size].twist.twist.linear.x
            rospy.logwarn("DECEL: vel[0]={:.2f}, vel[{}]={:.2f}".format(vel_start, size, vel_end))

        return temp

    def get_waypoint_velocity(self, waypoint):
        return waypoint.twist.twist.linear.x

    def set_waypoint_velocity(self, waypoints, waypoint, velocity):
        waypoints[waypoint].twist.twist.linear.x = velocity

    def distance(self, waypoints, wp1, wp2):
        dist = 0
        dl = lambda a, b: math.sqrt(((a.x-b.x)**2) + ((a.y-b.y)**2)  + ((a.z-b.z)**2))
        for i in range(wp1, wp2+1):
            dist += dl(waypoints[wp1].pose.pose.position, waypoints[i].pose.pose.position)
            wp1 = i
        return dist


if __name__ == '__main__':
    try:
        WaypointUpdater()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start waypoint updater node.')
