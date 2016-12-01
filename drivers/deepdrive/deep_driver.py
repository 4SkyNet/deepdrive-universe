import caffe
import os
from gtav_driver import GTAVDriver
from universe.spaces.joystick_event import JoystickAxisXEvent, JoystickAxisZEvent
import logging
logger = logging.getLogger()

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


class DeepDriver(GTAVDriver):
    def __init__(self):
        super(DeepDriver, self).__init__()
        self.input_layer_name = 'images'

    def load_net(self):
            caffe.set_mode_gpu()
            model_def = os.path.join(DIR_PATH, 'deep_drive_model.prototxt')
            model_weights = os.path.join(DIR_PATH, 'caffe_deep_drive_train_iter_35352.caffemodel')
            self.net = caffe.Net(model_def,  # defines the structure of the model
                                 model_weights,  # contains the trained weights
                                 caffe.TEST)  # use test mode (e.g., don't perform dropout)
            transformer = caffe.io.Transformer({'data': self.net.blobs[self.input_layer_name].data.shape})
            transformer.set_transpose('data', (2, 0, 1))  # convert to Channel Width Height
            transformer.set_channel_swap('data', (2, 1, 0))  # swap channels from RGB to BGR
            self.image_transformer = transformer

    def get_next_action_n(self, net_out, info):
        spin, direction, speed, speed_change, steer, throttle = net_out['gtanet_fctop'][0]
        steer = -float(steer)
        steer_dead_zone = 0.2

        # Add dead zones
        if steer > 0:
            steer += steer_dead_zone
        elif steer < 0:
            steer -= steer_dead_zone

        logger.info('steer %f', steer)
        x_axis_event = JoystickAxisXEvent(steer)
        if 'n' in info and 'speed' in info['n'][0]:
            current_speed = info['n'][0]['speed']
            desired_speed = speed / 0.05  # Denormalize per deep_drive.h in deepdrive-caffe
            if desired_speed < current_speed:
                logger.info('braking')
                throttle = self.throttle - (current_speed - desired_speed) * 0.085  # Magic number
                throttle = max(throttle, 0.0)
            else:
                throttle += 13. / 50.  # Dead zone

            z_axis_event = JoystickAxisZEvent(float(throttle))
            logging.info('throttle %s', throttle)
        else:
            z_axis_event = JoystickAxisZEvent(0)
            logging.warn('cannot determine speed of car, coasting')
        next_action_n = [[x_axis_event, z_axis_event]]

        self.throttle = throttle
        self.steer = steer

        return next_action_n

    def set_net_input(self, image):
        # print(image)
        transformed_image = self.image_transformer.preprocess('data', image)
        self.net.blobs[self.input_layer_name].data[...] = transformed_image