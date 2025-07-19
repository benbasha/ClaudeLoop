#!/usr/bin/env python3
import pty
import os
import sys
import select
import subprocess
import fcntl

def main():
    # Parse command line arguments
    skip_permissions = '--skip-permissions' in sys.argv
    
    # Spawn Claude with a proper PTY
    master, slave = pty.openpty()
    
    # Start Claude process with the slave PTY as its controlling terminal
    claude_args = ['claude']
    if skip_permissions:
        claude_args.append('--dangerously-skip-permissions')
    
    claude_process = subprocess.Popen(
        claude_args,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        close_fds=True,
        preexec_fn=os.setsid
    )
    
    # Close the slave end in the parent process
    os.close(slave)
    
    # Set stdin to non-blocking mode
    stdin_flags = fcntl.fcntl(sys.stdin.fileno(), fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, stdin_flags | os.O_NONBLOCK)
    
    try:
        while claude_process.poll() is None:
            # Use select to handle both reading from master and stdin
            # Use None for blocking select (waits until data is available)
            # This prevents busy-waiting and reduces CPU usage
            ready, _, _ = select.select([master, sys.stdin], [], [])
            
            if master in ready:
                try:
                    # Read from Claude and write to stdout
                    data = os.read(master, 1024)
                    if data:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
                except OSError:
                    break
            
            if sys.stdin in ready:
                try:
                    # Read from stdin and write to Claude
                    # Read more data at once for better performance
                    data = sys.stdin.buffer.read(1024)
                    if data:
                        # Debug: print what we're sending to Claude
                        # Use stderr for debug output to avoid interfering with stdout data flow
                        # between the PTY and Claude - stdout is reserved for actual program output
                        sys.stderr.write(f"[PTY] Sending to Claude: {repr(data)}\n")
                        sys.stderr.flush()
                        os.write(master, data)
                except (OSError, BlockingIOError):
                    break
                    
    except KeyboardInterrupt:
        pass
    finally:
        # Clean up
        claude_process.terminate()
        claude_process.wait()
        os.close(master)

if __name__ == '__main__':
    main() 