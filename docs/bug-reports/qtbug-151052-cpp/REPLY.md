Thanks — I have now retested with Qt 6.12.0 and a development source build, and
attached a standalone C++ reproducer (`qtbug-151052-cpp.zip`). Neither the client
nor the synthetic portal uses Python, AutoTalk code or Qt private APIs.

Results using the same C++ source and injected OpenPipeWireRemote failure:

- **Unpatched Qt 6.10.2:** reproduces SIGSEGV on the first QScreenCapture::stop().
  The attached C++ backtrace reaches pw_thread_loop_stop() through
  QPipeWireCapture::setActiveInternal(bool).
- **Official Qt 6.12.0 Linux GCC SDK:** 20 consecutive failed-initialization,
  stop and destruction cycles complete successfully, exit 0.
- **Development Qt 6.13.0 alpha1:** the same 20 cycles complete successfully,
  exit 0. Source commits: qtbase `e26d5a8eee0078c24e6a2a741b7a0df18824281a`,
  qtmultimedia `2169149ee8e37ad58f088f013f141acee14d9918`,
  qtshadertools `0e2e83bc3de2530b998b9d2547beae68f7178ea1`.

So I can no longer reproduce the reported SIGSEGV on either newer version.
Both still emit `QObject::killTimer: Timers cannot be stopped from another
thread` and `QObject::startTimer: Timers cannot be started from another thread`;
I have left those warnings in the logs.

The fixture runs on a private D-Bus session. It accepts CreateSession,
SelectSources and Start, then returns a deterministic D-Bus error from
OpenPipeWireRemote. The client requires that exact error before calling stop
and destroying the capture objects. No real screen sharing or audio is needed.
The README has CMake/run commands, and RESULTS.md records versions, environment,
build details and logs.

I tested 6.10.2 and 6.12.0 with XCB/Xvfb and repeated both with the offscreen
plugin used for the development build; the results agree. This checks the
reported partial-initialization cleanup path, not full desktop recording.
