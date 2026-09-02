# ROMI-ROS2 Tutorials

Step-by-step setup guides for students who are brand new to Linux, Windows
Subsystem for Linux (WSL), Docker, and ROS 2. Pick the guide that matches the
laptop/desktop you will be doing your development work on. Both guides walk
you through the exact same overall pipeline, just with tools appropriate to
your operating system:

1. Install the tools you need on your computer.
2. Flash the ROMI 32U4 control board with the class Arduino firmware.
3. Flash the provided Raspberry Pi image onto a microSD card.
4. Clone this repository and build the ROS 2 workspace on your computer.
5. Sync the workspace to the Raspberry Pi and build it there too.
6. Verify everything works by driving the robot with the keyboard.

| Guide | Use this if... |
|---|---|
| [Linux Setup Guide](linux-setup.md) | Your computer already runs Linux (e.g. Ubuntu), or you are comfortable installing it. Uses Docker + a VS Code Dev Container. |
| [Windows Setup Guide](windows-setup.md) | Your computer runs Windows. Uses WSL2 with Ubuntu 22.04 and installs ROS 2 directly (no Docker container). |

Both guides assume you have never used Linux, ROS 2, or this repository
before, and explain each command in plain language. If you get stuck, re-read
the surrounding paragraph slowly, double-check for typos in the command you
typed, and ask your instructor or TA for help — do not just keep re-running
the same command.

See the top-level [README.md](../README.md) for the full technical reference
(all launch files, parameters, and advanced options) once you are comfortable
with the basics.
