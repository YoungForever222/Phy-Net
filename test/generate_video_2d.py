import math

import numpy as np
import tensorflow as tf
import cv2

import sys
sys.path.append('../')

from model.ring_net import *
from model.loss import *
from utils.experiment_manager import make_checkpoint_path
from systems.fluid_createTFRecords import generate_feed_dict
from systems.lattice_utils import *
import random
import time
from tqdm import *

FLAGS = tf.app.flags.FLAGS

# get restore dir
RESTORE_DIR = make_checkpoint_path(FLAGS.base_dir, FLAGS)

# video init
fourcc = cv2.cv.CV_FOURCC('m', 'p', '4', 'v') 
video = cv2.VideoWriter()

# shape of test simulation
shape = FLAGS.test_dimensions.split('x')
shape = map(int, shape)

# 2d or not
if len(shape) == 2:
  d2d = True

# open video
if d2d:
  success = video.open('figs/' + str(shape[0]) + "x" + str(shape[1]) + '_2d_video_.mov', fourcc, 4, (3*shape[0], shape[1]), True)
else:
  success = video.open('figs/' + str(shape[0]) + "x" + str(shape[1]) + "x" + str(shape[2]) + '_3d_video.mov', fourcc, 4, (3*shape[2], shape[1]), True)
if success:
  print("opened video stream to fluid_flow.mov")
else:
  print("unable to open video, make sure video settings are correct")
  exit()

def evaluate():
  """ Eval the system"""
  with tf.Graph().as_default():
    # make inputs
    state, boundary = inputs(empty=True, shape=shape)

    # unwrap
    y_1, small_boundary_mul, small_boundary_add, x_2, y_2 = continual_unroll_template(state, boundary)

    # restore network
    variables_to_restore = tf.all_variables()
    saver = tf.train.Saver(variables_to_restore)
    sess = tf.Session()
    ckpt = tf.train.get_checkpoint_state(RESTORE_DIR)
    if ckpt and ckpt.model_checkpoint_path:
      print("restoring file from " + ckpt.model_checkpoint_path)
      saver.restore(sess, ckpt.model_checkpoint_path)
    else:
      print("no chekcpoint file found from " + RESTORE_DIR + ", this is an error")
      exit()

    # get frame
    lveloc = get_lveloc(FLAGS.lattice_size)
    state_feed_dict, boundary_feed_dict = generate_feed_dict(1, shape, FLAGS.lattice_size, 'fluid_flow_' + str(shape[0]) + 'x' + str(shape[1]) + '_test', 0, 0)
    feed_dict = {state:state_feed_dict, boundary:boundary_feed_dict}
    y_1_g, small_boundary_mul_g, small_boundary_add_g = sess.run([y_1, small_boundary_mul, small_boundary_add], feed_dict=feed_dict)
    last_step_frame_true = 0.0

    # generate video
    for step in tqdm(xrange(FLAGS.video_length)):
      # calc generated frame compressed state
      y_1_g, x_2_g = sess.run([y_2, x_2],feed_dict={y_1:y_1_g, small_boundary_mul:small_boundary_mul_g, small_boundary_add:small_boundary_add_g})

      # get normalized velocity
      x_2_g = x_2_g[0]
      if d2d:
        velocity_generated = lattice_to_vel(pad_2d_to_3d(x_2_g), lveloc)
      frame_generated = vel_to_norm_vel(velocity_generated)
      frame_generated = frame_generated[:,:,0,:]
     
      # get true normalized velocity 
      state_feed_dict, boundary_feed_dict = generate_feed_dict(1, shape, FLAGS.lattice_size, 'fluid_flow_' + str(shape[0]) + 'x' + str(shape[1]) + '_test', 0, 0+step)
      state_feed_dict = state_feed_dict[0]
      if d2d:
        state_feed_dict = pad_2d_to_3d(state_feed_dict)
      velocity_true = lattice_to_vel(state_feed_dict, lveloc) #keep first dim on and call it z
      frame_true = vel_to_norm_vel(velocity_true)
      frame_true = frame_true[:,:,0,:] 

      # make frame for video
      frame = np.concatenate([frame_generated, frame_true, np.abs(frame_generated - frame_true)], 1)
      frame = np.concatenate([frame, frame, frame], axis=2)
      frame = np.uint8(np.minimum(np.maximum(0, frame*255.0*10.0), 255)) # scale

      # write frame to video
      video.write(frame)

    # release video
    video.release()
    cv2.destroyAllWindows()

       
def main(argv=None):  # pylint: disable=unused-argument
  evaluate()


if __name__ == '__main__':
  tf.app.run()
