import os
import pwd
import getpass

def get_user(home_at=['/home','/Users' ,'/var', '/opt', '/usr']):
    """Try to find the user who executed the script originally.
    
    :param home_at: List of directories containing home directories
    :return: User who probably run the script as pwd struct

    It will look the process tree up until it finds a uid that is not zero.
    If the uid has his home directory in any path of ``home_at`` it will
    return this uid. If ``home_at`` is None, no home directory checking
    will be done.
    """
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
    uid = os.getuid()
    ppid = os.getpid()

    return pwd.getpwuid(uid), ppid
