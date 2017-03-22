# -*- coding: utf-8 -*-
"""
Created on Tue Mar 21 17:04:11 2017

@author: Will
"""
import serial
import struct
import numpy as np
from nplab.instrument.apt_virtual_com_port import APT_VCP
from nplab.instrument.stage import Stage
import types
import time

DC_status_motors = ['BBD102/BBD103', 'TDC001']


class APT_VCP_motor(APT_VCP, Stage):
    """
    This class handles all the basic communication with APT virtual com ports
    """

    # status_bit_mask = {0x00000001 : 'forward (CW) hardware limit switch is active',
    #                     0x00000002 : 'reverse (CCW) hardware limit switch is active',
    #                     0x00000004 : 'forward (CW) software limit switch is active',
    #                     0x00000008 : 'reverse (CCW) software limit switch is active',
    #                     0x00000010 : 'in motion, moving forward (CW)',
    #                     0x00000020 : 'in motion, moving reverse (CCW)',
    #                     0x00000040 : 'in motion, jogging forward (CW)',
    #                     0x00000080 : 'in motion, jogging reverse (CCW)',
    #                     0x00000100 : 'motor connected',
    #                     0x00000200 : 'in motion, homing',
    #                     0x00000400 : 'homed (homing has been completed)',
    #                     0x00001000 : 'interlock state (1 = enabled)' }

    # TODO: the homed function and the move_completed function (I do not understand how they work)

    def __init__(self, port=None, source=0x01, destination=None, verbosity=True, use_si_units=False):
        """
        Set up the serial port, setting source and destinations, verbosity and hardware info.
        """
        APT_VCP.__init__(self, port=port, source=source, destination=destination, verbosity=verbosity,
                         use_si_units=use_si_units)  # this opens the port
        Stage.__init__(self)
        if self.model[1] in DC_status_motors:
            # Set the bit mask for DC controllers
            self.status_bit_mask = np.array([[0x00000001, 'forward hardware limit switch is active'],
                                             [0x00000002, 'reverse hardware limit switch is active'],
                                             [0x00000010, 'in motion, moving forward'],
                                             [0x00000020, 'in motion, moving reverse'],
                                             [0x00000040, 'in motion, jogging forward'],
                                             [0x00000080, 'in motion, jogging reverse'],
                                             [0x00000200, 'in motion, homing'],
                                             [0x00000400, 'homed (homing has been completed)'],
                                             [0x00001000, 'tracking'],
                                             [0x00002000, 'settled'],
                                             [0x00004000, 'motion error (excessive position error)'],
                                             [0x01000000, 'motor current limit reached'],
                                             [0x80000000, 'channel is enabled']])
            self.velocity_scaling_factor = 204.8  # for converting velocity to mm/sec
        else:
            # Set the bit mask for normal motor controllers
            self.status_bit_mask = {0x00000001: 'forward (CW) hardware limit switch is active',
                                    0x00000002: 'reverse (CCW) hardware limit switch is active',
                                    0x00000004: 'forward (CW) software limit switch is active',
                                    0x00000008: 'reverse (CCW) software limit switch is active',
                                    0x00000010: 'in motion, moving forward (CW)',
                                    0x00000020: 'in motion, moving reverse (CCW)',
                                    0x00000040: 'in motion, jogging forward (CW)',
                                    0x00000080: 'in motion, jogging reverse (CCW)',
                                    0x00000100: 'motor connected',
                                    0x00000200: 'in motion, homing',
                                    0x00000400: 'homed (homing has been completed)',
                                    0x00001000: 'interlock state (1 = enabled)'}

    '''MOVEMENT'''

    def home(self):
        self.write(0x0443)
        # TODO: wait until home completed (0x0444)

    def move(self, pos, axis=None, relative=False):
        if axis is None:
            axis = 1
        data = bytearray(struct.pack('<HL', self.channel_number_to_identity[axis], pos))
        if relative:
            self.write(0x0448, data=data)
        else:
            self.write(0x0453, data=data)
            # TODO: wait until move completed (0x0464)

    '''PARAMETERS'''

    # def convert_to_SI_position(position):
    #     '''This is motor and controller specific and therefore need to be subclassed '''
    #     raise NotImplementedError
    #
    # def convert_to_APT_position(position):
    #     '''This is motor and controller specific and therefore need to be subclassed '''
    #     raise NotImplementedError
    #
    # def convert_to_SI_velocity(velocity):
    #     '''This is motor and controller specific and therefore need to be subclassed '''
    #     raise NotImplementedError
    #
    # def convert_to_APT_velocity(velocity):
    #     '''This is motor and controller specific and therefore need to be subclassed '''
    #     raise NotImplementedError
    #
    # def convert_to_SI_acceleration(acceleration):
    #     '''This is motor and controller specific and therefore need to be subclassed '''
    #     raise NotImplementedError
    #
    # def convert_to_APT_acceleration(acceleration):
    #     '''This is motor and controller specific and therefore need to be subclassed '''
    #     raise NotImplementedError

    def get_status_update(self, channel_number=1):
        if self.model[1] in DC_status_motors:
            returned_message = self.query(0x0490, param1=self.channel_number_to_identity[channel_number])
        else:
            returned_message = self.query(0x0480, param1=self.channel_number_to_identity[channel_number])
        self.update_status(returned_message['data'])
        # channel,position,EncCount,status_bits =  struct.unpack(returned_message, '<ILLH')

    def update_status(self, returned_message):
        '''This  command should update device properties from the update message
            however this has to be defined for every device as the status update format
            and commands vary, 
            please implement me
            Args:
                The returned message from a status update request           (dict)
        '''
        if self.model[1] in DC_status_motors:
            channel, position, velocity, Reserved, status_bits = struct.unpack('<HLHHI', returned_message)
            # self.position = position
            # self.velocity = velocity / self.velocity_scaling_factor
            self.status = self.status_bit_mask[np.where(self.unpack_binary_mask(status_bits))]
        else:
            channel, position, EncCount, status_bits = struct.unpack(returned_message, '<ILLH')
            self.position = position  #
            self.EncCount = EncCount
            self.status = self.status_bit_mask.values()[self.upack_binary_mask(status_bits) == True]

    def staying_alive(self):
        """Keeps the motor controller from thinking the Pc has crashed """
        self.write(0x0492)

    def init_no_flash_programming(self):
        """ This message must be sent on startup to tell the controller 
        the source and destination address - The manual says this MUST be
        sent as part of the intialisation process
        
        Labled as: MGMSG_HW_NO_FLASH_PROGRAMMING
        """
        self.write(0x0018)

    def get_position(self, channel_number=1):
        '''Sets/Gets the live position count in the controller
            generally this should not be used to set the position 
            instead the controller should determine its own position
            by performing a homing manoeuvre
            Args:
                postion:    (float) this is the real position value
                            which is then converted to APT units within the setter
                channel_number:     (int) This defaults to 1
        '''
        returned_message = self.query(0x0411, param1=self.channel_number_to_identity[channel_number])
        data = returned_message['data']
        channel_id, position = struct.unpack('<HL', data)
        # position = self.convert_to_SI_position(position)
        return position

    def set_position(self, position, channel_number=1):
        position = self.convert_to_APT_position(position)
        data = bytearray(struct.pack('<HL', self.channel_number_to_identity[channel_number], position))
        self.write(0x0410, data=data)

    position = property(get_position, set_position)

    def get_encoder_counts(self, channel_number=1):
        '''Sets/Gets the live encoder count in the controller
            generally this should not be used to set the encoder value 
            instead the controller should determine its own position by
            performing a homing manoeuvre
            Args:
                encoder_counts:    (int) this is the encoder counts
                channel_number:     (int) This defaults to 1
        '''
        returned_message = self.query(0x040A, param1=self.channel_number_to_identity[channel_number])
        data = returned_message['data']
        channel_id, encoder_counts = struct.unpack('<HL', data)
        return encoder_counts

    def set_encoder_counts(self, encoder_counts, channel_number=1):
        data = bytearray(struct.pack('<HL', self.channel_number_to_identity[channel_number], encoder_counts))
        self.write(0x0409, data=data)

    encoder_counts = property(get_encoder_counts, set_encoder_counts)

    # def get_velocity_params(self, channel_number=1):
    #     """Trapezoidal velocity parameters for the specified
    #     motor channel. For DC servo controllers, the velocity is set in
    #     encoder counts/sec and acceleration is set in encoder
    #     counts/sec/sec.For stepper motor controllers the velocity
    #     is set in microsteps/sec and acceleration is set in microsteps/sec/sec.
    #     However, we have handled the conversions therefore SI are used.
    #     Args:
    #         velocity_params(dict) containing:
    #             channel_num (int)       :   the channel number
    #             min_velocity(float)     :   Minimum velocity in SI units
    #             acceleration(float)     :   acceleration in SI units
    #             max_velocity(float)     :   maximum velocity in SI units
    #         """
    #     returned_message = self.query(0x0414, param1=self.channel_number_to_identity[channel_number])
    #     data = returned_message['data']
    #     channel_id, min_vel, acceleration, maximum_vel = struct.unpack('<HLLL', data)
    #     velocity_parms = {'channel_num': channel_number, 'min_velocity': self.convert_to_SI_velocity(min_vel),
    #                       'acceleration': self.convert_to_SI_acceleration(acceleration),
    #                       'max_velocity': self.convert_to_SI_velocity(maximum_vel)}
    #     return velocity_parms
    #
    # def set_velocity_params(self, velocity_params, channel_number=1):
    #
    #     data = struct.pack('<HLLL',
    #                        self.channel_number_to_identity[velocity_params['channel_num']],
    #                        self.convert_to_APT_velocity(velocity_params['min_velocity']),
    #                        self.convert_to_APT_acceleration(velocity_params['acceleration']),
    #                        self.convert_to_APT_velocity(velocity_params['max_velocity']),
    #                        )
    #     self.write(0x0413, data=data)
    #
    # velocity_params = property(get_velocity_params,
    #                            set_velocity_params)  # not sure how this will work with channel inputs may only work when channel = 1
    #
    # def get_jog_params(self, channel_number=1):
    #     """Used to set the velocity jog parameters for the specified motor
    #         channel, For DC servo controllers, values set in encoder counts.
    #         For stepper motor controllers the values is set in microsteps. However,
    #         here we have converted them to SI units
    #     Args:
    #         jog_param(dict) contains
    #             channel_num (int)       :   channel number
    #             jog_mode (int)          :   jog mode 1 for cont 2 for single step
    #             jog_step_size (float)   :   jog step size converted to SI
    #             jog_min_velocity(float) :   minimum velocity converted to SI
    #             jog_max_velovity(float) :   maximum velocity converted to SI
    #             jog_stop_mode(int)      :   1 for immediate 2 for profiled stop
    #
    #     """
    #     returned_message = self.query(0x0417, param1=self.channel_number_to_identity[channel_number])
    #     data = returned_message['data']
    #     data = struct.unpack('<HHLLLLH', data)
    #     jog_params = {'channel_num': data[0], 'jog_mode': data[1],
    #                   'jog_step_size': self.convert_to_SI_position(data[2]),
    #                   'jog_min_velocity': self.convert_to_SI_velocity(data[3]),
    #                   'jog_acceleration': self.convert_to_SI_acceleration(data[4]),
    #                   'jog_max_velocity': self.convert_to_SI_velocity(data[5]),
    #                   'jog_stop_mode': data[6]}
    #     return jog_params
    #
    # def set_jog_params(self, jog_params, channel_number=1):
    #     data = struct.pack('<HHLLLLH',
    #                        self.channel_number_to_identity[jog_params['channel_num']],
    #                        jog_params['jog_mode'],
    #                        self.convert_to_APT_position(jog_params['jog_step_size']),
    #                        self.convert_to_APT_velocity(jog_params['jog_min_velocity']),
    #                        self.convert_to_APT_acceleration(jog_params['jog_acceleration']),
    #                        self.convert_to_APT_velocity(jog_params['jog_max_velocity']),
    #                        jog_params['jog_stop_mode'])
    #     self.write(0x0416, data=data)
    #
    # jog_params = property(get_jog_params, set_jog_params)

    # def get_power_params(self, channel_number=1):
    #     """
    #     The power needed to hold a motor in a fixed position is much smaller than that required for a move. It is good
    #     practice to decrease the power in a stationary motor in order to reduce heating, and thereby minimize thermal
    #     movements caused by expansion. This message sets a reduction factor for the rest power and the move power values
    #     as a percentage of full power. Typically, move power should be set to 100% and rest power to a value
    #     significantly less than this.
    #
    #     Args:
    #         channel_number:
    #
    #     Returns:
    #         power_params (dict):
    #             channel_num (int)   : channel being addressed
    #             RestFactor (int)    : the phase power value when the motor is at rest, in the range 1 to 100
    #                                   (i.e. 1% to 100% of full power)
    #             MoveFactor (int)    : the phase power value when the motor is moving, in the range 1 to 100
    #     """
    #     returned_message = self.query(0x0427, param1=self.channel_number_to_identity[channel_number])
    #     data = returned_message['data']
    #     data = struct.unpack('<HHH', data)
    #     power_params = {'channel_num': data[0],
    #                   'RestFactor': data[1],
    #                   'MoveFactor': data[2]}
    #     return power_params
    #
    # def set_power_params(self, power_params, channel_number=None):
    #     if channel_number is None:
    #         channel_number = power_params['channel_num']
    #     data = struct.pack('<HHH',
    #                        self.channel_number_to_identity[channel_number],
    #                        power_params['RestPower'],
    #                        power_params['MovePower'])
    #     self.write(0x0426, data=data)
    #
    # power_params = property(get_power_params, set_power_params)

    # def get_gen_move_params(self, channel_number=1):
    #     """
    #     Used to set the general move parameters for the specified motor
    #     channel. At this time this refers specifically to the backlash settings.
    #
    #     Args:
    #         channel_number:
    #
    #     Returns:
    #         gen_move_params (dict):
    #             channel_num (int)       :   channel being addressed
    #             backlash_distance (int) :   The value of the backlash distance as a 4 byte signed
    #                                         integer, which specifies the relative distance in position
    #                                         counts. The scaling between real time values and this
    #                                         parameter is detailed in Section 8.
    #     """
    #     returned_message = self.query(0x043B, param1=self.channel_number_to_identity[channel_number])
    #     data = returned_message['data']
    #     data = struct.unpack('<HL', data)
    #     gen_move_params = {'channel_num': data[0],
    #                     'backlash_distance': data[1]}
    #     return gen_move_params
    #
    # def set_gen_move_params(self, gen_params, channel_number=None):
    #     if channel_number is None:
    #         channel_number = gen_params['channel_num']
    #     data = struct.pack('<HL',
    #                        self.channel_number_to_identity[channel_number],
    #                        gen_params['backlash_distance'])
    #     self.write(0x043C, data=data)
    #
    # gen_move_params = property(get_gen_move_params, set_gen_move_params)
    def convert(self, value, from_, to_):
        print 'Not doing anything from ', from_, ' to ', to_
        return value

    def make_parameter(self, param_dict):
        """

        Args:
            param_dict:
                name        :   internal name that you want the parameter to have
                set         :   setter function
                get         :   getter function
                structure   :   binary structure of the data packets
                param_names :   names of the parameters in the structure

        Returns:

        """

        def getter(selfie, channel_number=1):
            returned_message = selfie.query(param_dict['get'], param1=selfie.channel_number_to_identity[channel_number])
            data = returned_message['data']
            data = struct.unpack('<' + param_dict['structure'], data)
            params = {}
            index = 0
            for name in param_dict['param_names']:
                if type(name) == str:
                    params[name] = data[index]
                elif type(name) == list:
                    params[name[0]] = selfie.convert(data[index], 'counts', name[1])
                index += 1
            return params

        def setter(selfie, params, channel_number=None):
            if channel_number is None:
                channel_number = params['channel_num']
            unstructured_data = ['<' + param_dict['structure'],
                                 selfie.channel_number_to_identity[channel_number]]
            for name in param_dict['param_names']:
                if name != 'channel_num':
                    if type(name) == str:
                        unstructured_data += [params[name]]
                    elif type(name) == list:
                        unstructured_data += [selfie.convert(params[name[0]], name[1], 'counts')]
            data = struct.pack(*unstructured_data)
            selfie.write(param_dict['set'], data=data)

        setattr(self, 'get_' + param_dict['name'], types.MethodType(getter, self))
        setattr(self, 'set_' + param_dict['name'], types.MethodType(setter, self))
        setattr(self, param_dict['name'], property('get_' + param_dict['name'], 'set_' + param_dict['name']))

    def make_all_parameters(self):
        # TODO: add all the documentation for each of these parameters
        self.make_parameter(dict(name='velocity_params', set=0x0413, get=0x0414, structure='HLLL',
                                 param_names=['channel_num', ['min_velocity','velocity'], ['acceleration','acceleration'], ['max_velocity','velocity']]))
        self.make_parameter(dict(name='jog_params', set=0x0416, get=0x0417, structure='HHLLLLH',
                                 param_names=['channel_num', ['jog_step_size','distance'], ['jog_min_velocity','velocity'], ['jog_acceleration','acceleration'],
                                              ['jog_max_velocity','velocity'], 'jog_stop_mode']))
        self.make_parameter(dict(name='gen_move_params', set=0x043C, get=0x043B, structure='HL',
                                 param_names=['channel_num', 'backlash']))
        self.make_parameter(dict(name='power_params', set=0x0426, get=0x0427, structure='HHH',
                                 param_names=['channel_num', 'RestPower', 'MovePower']))
        self.make_parameter(dict(name='move_rel_params', set=0x0446, get=0x0447, structure='HL',
                                 param_names=['channel_num', 'rel_dist']))
        self.make_parameter(dict(name='move_abs_params', set=0x0451, get=0x0452, structure='HL',
                                 param_names=['channel_num', 'abs_dist']))
        self.make_parameter(dict(name='home_params', set=0x0441, get=0x0442, structure='HHHLL',
                                 param_names=['channel_num', 'direction', 'limit_switch', 'velocity', 'offset']))
        # self.make_parameter(dict(name=, set=, get=, structure=, param_names=['channel_num']))
        # self.make_parameter(dict(name=, set=, get=, structure=, param_names=['channel_num']))
        # self.make_parameter(dict(name=, set=, get=, structure=, param_names=['channel_num']))
        # self.make_parameter(dict(name=, set=, get=, structure=, param_names=['channel_num']))


if __name__ == '__main__':
    # microscope_stage = APT_VCP_motor(port='COM12', source=0x01, destination=0x21)

    tdc_cube = APT_VCP_motor(port='COM20', source=0x01, destination=0x50)
    # print tdc_cube.channel_number_to_identity['1']
    # tdc_cube.get_status_update()
    # print 'Status: ', tdc_cube.status
    # print 'Position: ', tdc_cube.get_position()

    tdc_cube.make_all_parameters()
    print tdc_cube.get_velocity_params()
    print tdc_cube.velocity_params
    # print tdc_cube.get_gen_move_params()
    # print tdc_cube.get_haha()

    # tdc_cube.home()

    # tdc_cube.move(0)
    # time.sleep(10)
