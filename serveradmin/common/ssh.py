import subprocess

SSH_OPTS = (
    '-o BatchMode=yes',
    '-o StrictHostKeyChecking=no',  # You shouldn't use it ...
    '-o IdentitiesOnly=yes',
    '-o ConnectTimeout=5',
)


def execute_ssh_popen(host, ssh_key, cmd, **popen_opts):
    if isinstance(cmd, list):
        cmd = tuple(cmd)
    else:
        cmd = (cmd,)

    call = ('/usr/bin/ssh', '-i', ssh_key) + SSH_OPTS + (host,) + cmd
    return subprocess.Popen(call, **popen_opts)


def execute_ssh(host, ssh_key, cmd):
    p = execute_ssh_popen(host, ssh_key, cmd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    return p.wait(), stdout, stderr
