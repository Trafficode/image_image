# -*- coding: utf-8 -*-
from camcam import CamCam
import queue
import json
import os
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

CamConfig = None


def confif_reload():
    config = None
    if os.path.exists("cam_config.json"):
        try:
            config_f = open("cam_config.json", "r")
            config = json.load(config_f)
            config_f.close()
        except:
            print("\n\tLoad cam_config.json failed, bad json format...\n")
    else:
        print("\n\tFaile cam_config.json not found! Create based on template...\n")
    return (config)


CamConfig = confif_reload()
if not CamConfig:
    exit(0)

logger = logging.getLogger("main")

if __name__ == "__main__":
    print("# --------------------------------------------------- #")
    print("# Welcome in CamApp, aplication to camera capture\n")
    cameras = []
    for cam in CamConfig:
        cam = CamCam(cam["id"], cam["video"], "../storage",
                     cam["width"], cam["height"], cam["br"], cam["br_range"])
        cameras.append(cam)
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
                CamConfig = confif_reload()
                if len(param) == 1:
                    angle = float(param[0])
                else:
                    angle = 0
                for cam in cameras:
                    details = cam.picture_take(_angle=angle)
                    print(details)

            elif "save" == cmd:
                CamConfig = confif_reload()
                work_queue = queue.Queue()
                for cam in cameras:
                    details = cam.picture_match_asynq(work_queue, _save=True)
                for _ in range(3):
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
    for cam in cameras:
        print("cam_%d exit status: %s" % (cam.id, str(cam.exit())))

print("\n\tThanks for using CamApp:)")

###############################################################################
# END OF FILE
###############################################################################
