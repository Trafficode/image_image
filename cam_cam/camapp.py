# -*- coding: utf-8 -*-
from camcam import CamCam
import queue

import logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s :: %(name)8s :: %(levelname)s :: %(message)s"
)

# 3264X2448 MJPEG 15fps YUY2 2fps
# 3200X2400 MJPEG 20fps YUY2 3fps
# 2592X1944 MJPEG 15fps YUY2 3fps
# 2048X1536 MJPEG 20fps YUY2 3fps
# 1600X1200 MJPEG 20fps YUY2 10fps
# 1280X960  MJPEG 20fps YUY2 10fps
# 1024X768  MJPEG 30fps YUY2 10fps
# 800X600   MJPEG 30fps YUY2 30fps
# 640X480   MJPEG 30fps YUY2 30fps

logger = logging.getLogger("main")

# ATTRS{idProduct}=="8830"
# ATTRS{idVendor}=="32e4"

if __name__ == "__main__":
    print("# --------------------------------------------------- #")
    print("# Welcome in CamApp, aplication to camera capture\n")

    cam_a = CamCam(0, "video0", "../storage", 1920, 1080, 160, 2)
    while True:
        try:
            line = input("cmd> ").strip()
            if len(line) == 0:
                continue

            splited = line.split(" ", 1)
            cmd = splited[0]
            if len(splited) > 1:
                param = splited[1].strip().split()
            else:
                param = []

            if "exit" == cmd:
                break
            elif "cam" == cmd:
                angle = float(param[0])
                details = cam_a.picture_take(_angle=angle)
                print(details)
            elif "save" == cmd:
                work_queue = queue.Queue()
                cam_a.picture_match_asynq(work_queue, _save=True)
                try:
                    result = work_queue.get(timeout=2.0)
                    print("result: %s" % str(result))
                except queue.Empty:
                    print("No result got")
                work_queue.task_done()
        except KeyboardInterrupt:
            break
    print(".")
    print(".")
    print("cam_a exit status: ", cam_a.exit())

print("\n\tThanks for using CamApp:)")

###############################################################################
# END OF FILE
###############################################################################
