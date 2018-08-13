# -*- coding: utf-8 -*-
"""
Created on Wed Jun 11 12:28:18 2014

@author: Richard
"""

import sys
try:
    import uc480
except ImportError:
    explanation="""
WARNING: could not import the UC480 library.
    
Make sure you have installed the ThorLabs camera software, and copied in the
uc480 module.
We are using Python %d.%d, so get the corresponding package.
""" % (sys.version_info.major, sys.version_info.minor)
    print explanation
    raise ImportError(explanation) 
    
from nplab.instrument.camera import Camera, CameraParameter
from nplab.utils.notified_property import NotifiedProperty
    
class ThorLabsCamera(Camera):
    def __init__(self,capturedevice=0):
        self.cap=uc480.uc480()
        self.cap.connect(ID=capturedevice)
        
        super(ThorLabsCamera,self).__init__() #NB this comes after setting up the hardware
     
        
    def close(self):
        """Stop communication with the camera and allow it to be re-used."""
        super(ThorLabsCamera, self).close()
        self.cap.disconnect()
        
    def raw_snapshot(self, suppress_errors = False):
        """Take a snapshot and return it.  Bypass filters etc."""
        with self.acquisition_lock:
            return True, self.cap.acquire()
    
    def set_gain(self, gain):
        self.cap.set_gain(gain)
    def get_gain(self):
        return self.cap.get_gain()
    gain = NotifiedProperty(fget=get_gain, fset=set_gain, doc="Get or set the gain of the camera (0-100)")
        
    def set_exposure(self, value):
        self.cap.set_exposure(value)
    def get_exposure(self):
        return self.cap.get_exposure()
    exposure = NotifiedProperty(fget=get_exposure, fset=set_exposure, doc="Get or set the exposure in ms")
    
    def camera_parameter_names(self):
        """List the adjustable parameters of this camera"""
        return ['gain', 'exposure']

# Add properties to change the camera parameters, based on OpenCV's parameters.
# It may be wise not to do this, and to filter them instead...


if __name__ == '__main__':
    cam = ThorLabsCamera()
    cam.show_gui()
