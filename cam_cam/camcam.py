# -*- coding: utf-8 -*-
import logging
import time

import cv2
from numpy.linalg import norm
import numpy as np
import os
import threading
import imutils
from datetime import datetime


class CamCam(object):
    ''' CamCam '''

    def __init__(self, _id: int, _video: str, _save_path, _pw: int, _ph: int,
                 _target_br: int, _target_br_diff: int) -> None:
        self.logger = logging.getLogger(_video)
        self.id = _id
        self.video_port = _video
        self.target_br = _target_br
        self.target_br_diff = _target_br_diff
        self.cam_gain = self.__last_gain_read()
        self.last_take_status = {}
        self.picture_dst_path = os.path.join(_save_path,
                                             "samples_%d" % self.id)
        self.request_angle = 0
        self.request_save = False
        self.result_queue = None
        self.match_angles = []
        self.match_threshold = 0
        self.match_tpls = []

        if not os.path.exists(self.picture_dst_path):
            os.makedirs(self.picture_dst_path)

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

        self.match_request_evt = threading.Event()
        self.match_request_evt.clear()

        self.proc_tid = threading.Thread(target=self.__run, daemon=True)
        self.proc_tid.start()

    def exit(self) -> bool:
        exit_status = False
        self.exit_request_evt.set()
        self.exit_done_evt.wait(timeout=4.0)
        if self.exit_done_evt.is_set():
            exit_status = True
        return (exit_status)

    def picture_match_asynq(self, _result_queue, _match_threshold=0,
                            _save=False, _match_tpls=[], _match_angles=[]):
        if len(_match_angles) == 0:
            self.match_angles = [0]
        else:
            self.match_angles = _match_angles
        self.match_threshold = _match_threshold
        self.match_tpls = _match_tpls
        self.request_save = _save
        self.result_queue = _result_queue
        self.match_request_evt.set()

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

                if self.match_request_evt.is_set():
                    self.match_request_evt.clear()
                    result = {"id": self.id, "status": "ok", "match": {}}
                    picture = imutils.rotate(picture, angle=self.request_angle)

                    if self.request_save:
                        time = datetime.now().strftime("%H%M%S")
                        img_name = "sample_%d_%s.jpg" % (self.id, time)
                        img_path = os.path.join(
                            self.picture_dst_path, img_name)
                        cv2.imwrite(img_path, picture)

                    # try to match here...
                    for img_tpl in self.match_tpls:
                        for angle in self.match_angles:
                            match_result = self.__match_template(
                                img_tpl, picture, self.match_threshold, angle)
                            result["match"][img_tpl] = [angle, match_result]
                    self.result_queue.put_nowait(result)

                    self.match_angles = []
                    self.match_tpls = []
                    self.match_threshold = 0
                    self.request_angle = 0
                    self.request_save = False
                    self.result_queue = None

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

    def __match_template(self, _img_tpl, _img_detect, _threshold, _angle):
        '''
        _img_tpl: try to detect this image in _img_detect
        _img_detect: image under pressure
        _threshold: 0 < _threshold < 1.0 
        return:
            _result = {
                "detections": 0, 
                "highest": 0, 
                "duration": 0,
                "avg": 0
            }
        '''
        _result = {"detections": 0, "highest": 0, "duration": 0, "avg": 0}
        _tstart = time.time()
        main_img_rgb = cv2.imread(_img_detect)
        if _angle != 0:
            main_img_rgb = imutils.rotate(main_img_rgb, angle=_angle)

        main_img_gray = cv2.cvtColor(main_img_rgb,  cv2.COLOR_BGR2GRAY)
        templ_img_grey = cv2.imread(_img_tpl, 0)

        # Define a similarity threshold  that needs to be met for a pixel to be
        # considered a match
        template_matching_threshold = _threshold

        template_matching = cv2.matchTemplate(
            templ_img_grey, main_img_gray, cv2.TM_CCOEFF_NORMED)

        matched_pixels = np.where(
            template_matching > template_matching_threshold)   # type: ignore
        template_width, template_height = templ_img_grey.shape[::-1]

        # Obtain the x,y coordinates for the matched pixels meeting the
        # threshold conditions
        detections = []
        count = 0

        highest = 0.0
        buff = 0.0
        for (x, y) in zip(matched_pixels[1], matched_pixels[0]):
            count = count + 1
            matching = template_matching[y, x]
            buff += matching
            highest = max(highest, matching)
            match = {"TOP_LEFT_X": x,
                     "TOP_LEFT_Y": y,
                     "BOTTOM_RIGHT_X": x + template_width,
                     "BOTTOM_RIGHT_Y": y + template_height,
                     "MATCH_VALUE": matching,
                     "LABEL": "MATCH_{}".format(count),
                     "COLOR": (255, 0, 0)
                     }
            self.logger.info("%s", str(match))
            detections.append(match)

        detections_number = len(detections)
        _result["detections"] = detections_number
        _result["highest"] = round(highest, 3)
        if detections_number != 0:
            _result["avg"] = round(buff/detections_number, 3)
        else:
            _result["avg"] = 0

        # logger.info("Make a copy of original image")
        # image_with_detections = main_img_rgb.copy()
        # logger.info("Plot a rectangle around the dectected match using the coord")
        # for detection in detections:
        #     cv2.rectangle(
        #         image_with_detections,
        #         (detection["TOP_LEFT_X"], detection["TOP_LEFT_Y"]),
        #         (detection["BOTTOM_RIGHT_X"], detection["BOTTOM_RIGHT_Y"]),
        #         detection["COLOR"],
        #         2
        #     )
        # cv2.imwrite('match_detect.jpg', image_with_detections)
        _result["duration"] = round(time.time() - _tstart, 3)
        return (_result)
###############################################################################
# END OF FILE
###############################################################################
