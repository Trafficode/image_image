# -*- coding: utf-8 -*-
import logging
import time
import cv2
from numpy.linalg import norm
import numpy as np
import os
import threading
import imutils


class CamCam(object):
    ''' CamCam '''

    def __init__(self, _video: str, _pw: int, _ph: int, _target_br: int,
                 _target_br_diff: int) -> None:
        self.logger = logging.getLogger(_video)
        self.video_port = _video
        self.target_br = _target_br
        self.target_br_diff = _target_br_diff
        self.cam_gain = self.__last_gain_read()
        self.last_take_status = {}
        self.request_angle = 0

        self.cam = cv2.VideoCapture("/dev/%s" % self.video_port)
        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, _pw)
        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, _ph)
        self.cam.set(cv2.CAP_PROP_GAIN, self.cam_gain)

        self.exit_request_evt = threading.Event()
        self.exit_request_evt.clear()
        self.exit_done_evt = threading.Event()
        self.exit_done_evt.clear()

        self.picture_request_evt = threading.Event()
        self.picture_request_evt.clear()
        self.picture_done_evt = threading.Event()
        self.picture_done_evt.clear()

        self.proc_tid = threading.Thread(target=self.__run, daemon=True)
        self.proc_tid.start()

    def exit(self) -> bool:
        exit_status = False
        self.exit_request_evt.set()
        self.exit_done_evt.wait(timeout=4.0)
        if self.exit_done_evt.is_set():
            exit_status = True

        return (exit_status)

    def picture_take(self, _angle=0.0):
        take_status = {}
        self.request_angle = _angle
        self.picture_done_evt.clear()
        self.picture_request_evt.set()
        self.picture_done_evt.wait(timeout=4.0)
        if self.picture_done_evt.is_set():
            take_status = dict(self.last_take_status)
        return (take_status)

    def __run(self):
        self.logger.info("%s thread started", self.video_port)
        while True:
            try:
                if self.exit_request_evt.is_set():
                    if self.cam.isOpened():
                        self.cam.release()
                    break

                picture, take_status = self.__picture_take()
                if self.picture_request_evt.is_set():
                    self.picture_request_evt.clear()
                    self.last_take_status = take_status
                    img_name = "capture_%s.jpg" % self.video_port
                    picture = imutils.rotate(picture, angle=self.request_angle)
                    cv2.imwrite(img_name, picture)
                    self.picture_done_evt.set()
            except:
                self.logger.exception(
                    "CamCam %s thread failed", self.video_port)

        self.logger.info("%s thread exit", self.video_port)
        self.exit_done_evt.set()

    def __picture_take(self):
        take_try = 0
        take_status = {
            "status": "ok",
            "br": 0,
            "br_diff": 0,
            "try": 0,
            "gain": 0,
            "read_takes": 0
        }
        while True:
            self.cam.set(cv2.CAP_PROP_GAIN, self.cam_gain)
            ts = time.time()
            result, image = self.cam.read()
            read_takes = round(time.time() - ts, 3)

            image = cv2.cvtColor(image,  cv2.COLOR_BGR2GRAY)
            br = self.__br_compute(image)
            diff = round(br - self.target_br, 1)
            take_status = {
                "br": br,
                "br_diff": diff,
                "try": take_try,
                "gain": round(self.cam_gain, 1),
                "read_takes": read_takes,
                "fps": self.cam.get(cv2.CAP_PROP_FPS)
            }
            if abs(diff) < self.target_br_diff:
                self.__last_gain_save()
                take_status["status"] = "ok"
                break
            elif diff < 0:
                if self.cam_gain < 100:
                    self.cam_gain += round(abs(diff)/4, 1)
                else:
                    self.logger.info(
                        "failed to take picture, cam_gain already max")
                    take_status["status"] = "cam_gain max"
                    break
            elif diff > 0:
                if self.cam_gain > 0:
                    self.cam_gain -= round(diff/4, 1)
                else:
                    self.logger.info(
                        "failed to take picture, cam_gain already min")
                    take_status["status"] = "cam_gain min"
                    break

            if self.cam_gain < 0:
                self.cam_gain = 0
            elif self.cam_gain > 100:
                self.cam_gain = 100
        return (image, take_status)

    def __br_compute(self, _img) -> float:
        br = 0.0
        if len(_img.shape) == 3:
            # Colored RGB or BGR (*Do Not* use HSV images with this function)
            # create brightness with euclidean norm
            br = round(np.average(norm(_img, axis=2)) / np.sqrt(3), 1)
        else:
            # Grayscale
            br = round(np.average(_img), 1)
        return (br)

    def __last_gain_read(self) -> float:
        fn = "cam_gain_%s" % self.video_port
        cam_gain = 60
        if os.path.exists(fn):
            gain_f = open(fn, "r")
            cam_gain = float(gain_f.read())
            gain_f.close()
        return (cam_gain)

    def __last_gain_save(self) -> None:
        fn = "cam_gain_%s" % self.video_port
        gain_f = open(fn, "w")
        gain_f.write(str(self.cam_gain))
        gain_f.close()

###############################################################################
# END OF FILE
###############################################################################
