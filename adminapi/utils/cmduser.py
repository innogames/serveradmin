import os
import pwd

def get_user(home_at=['/home', '/var', '/opt', '/usr']):
    """Try to find the user who executed the script originally.

    :param home_at: List of directories containing home directories
    :return: User who probably run the script as pwd struct

    It will look the process tree up until it finds a uid that is not zero.
    If the uid has his home directory in any path of ``home_at`` it will
    return this uid. If ``home_at`` is None, no home directory checking
    will be done.
    """
    if os.path.exists('/proc'):
        return _get_user_proc(home_at)
    else:
        return _get_user_psutil()


def _get_user_proc(home_at):
    home_at = [home_dir + '/' for home_dir in home_at if home_dir[-1] != '/']

    pid = os.getpid()
    while True:
        pwd_info, ppid = _parse_status(pid)

        has_home = False
        if home_at is None:
            has_home = True
        elif any(pwd_info.pw_dir.startswith(home_dir) for home_dir in home_at):
            has_home = True

        if has_home:
            return pwd_info

        # We are at init :o
        if pid == 1:
            # Could not find a better user
            return pwd_info
        pid = ppid


def _parse_status(pid):
    uid = None
    ppid = None
    with open('/proc/{0}/status'.format(pid)) as f:
        for line in f:
            if line.startswith('Uid:'):
                uid = int(line.split()[1])
            elif line.startswith('PPid:'):
                ppid = int(line.split()[1])
            if not (uid is None or ppid is None):
                break
        else:
            # Should never happen, but who knows ;-)
            raise Exception('Could not find Uid/PPid in /proc/PID/status')
    return pwd.getpwuid(uid), ppid


def _get_user_psutil():
    import psutil
    uid = os.getuid()
    pid = os.getpid()
    ppid = pid
    while uid == 0:
        ppid = psutil.Process(ppid).ppid()
        uid, effective,saved =  psutil.Process(ppid).uids()
    return pwd.getpwuid(uid)
