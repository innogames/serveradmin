import os
import pwd
import psutil

def get_user():
    """Try to find the user who executed the script originally.
    
    If it was root-user - go up to the tree and find original user
    who run sudo su
    :return: User who probably run the script as pwd struct
    """
    uid = os.getuid()
    pid = os.getpid()
    ppid = pid
    while uid == 0:
        ppid = psutil.Process(ppid).ppid()
        uid, effective,saved =  psutil.Process(ppid).uids()
    return pwd.getpwuid(uid)
