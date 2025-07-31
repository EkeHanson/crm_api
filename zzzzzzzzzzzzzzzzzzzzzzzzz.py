#CREATE A SESSION:  http://127.0.0.1:9090/api/talent-engine/video-sessions/
from sympy import false, true


{
    "job_application_id": "PRO-5385"
}


#JOIN A SESSION:  http://127.0.0.1:9090/api/talent-engine/video-sessions/join/
{
    "session_id": "cce05108-2ed6-4cf4-bd35-45cb1d5be2ea"
}

#Toogle Mute A SESSION:  http://127.0.0.1:9090/api/talent-engine/video-sessions/toggle_mute/
{
    "session_id": "cce05108-2ed6-4cf4-bd35-45cb1d5be2ea",
    "mute": false
}

#GET SESSION DETAILS:  http://127.0.0.1:9090/api/talent-engine/video-sessions/<session_id>/

#Toggle Camera on a SESSION:  http://127.0.0.1:9090/api/talent-engine/video-sessions/toggle_camera/
{
    "session_id": "cce05108-2ed6-4cf4-bd35-45cb1d5be2ea",
    "camera_on": true
}

