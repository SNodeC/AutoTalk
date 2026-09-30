# Keeping KWin off the NVIDIA GPU

Investigation: 29 September 2026. No persistent desktop configuration changed.

## Proposed narrow configuration

The installed KWin 6.7.4 supports three separate controls:

| Control | Purpose |
| --- | --- |
| `KWIN_DRM_DEVICES` | Restrict display/KMS devices to Intel |
| `KWIN_RENDER_NODES` | Restrict KWin's render-device discovery to Intel |
| `KWIN_DISABLE_VULKAN=1` | Prevent KWin's Vulkan instance creation from independently enumerating NVIDIA |

Proposed user service drop-in:
`~/.config/systemd/user/plasma-kwin_wayland.service.d/10-intel-only.conf`

```ini
[Service]
Environment="KWIN_DRM_DEVICES=/dev/dri/by-path/pci-0000\\:00\\:02.0-card"
Environment="KWIN_RENDER_NODES=/dev/dri/by-path/pci-0000\\:00\\:02.0-render"
Environment="KWIN_DISABLE_VULKAN=1"
```

This is a proposal, not an installed or desktop-validated configuration.
The doubled backslashes intentionally pass escaped colons through systemd to
KWin's device-list parser. Both Intel symlinks exist; PCI identity avoids
relying on the order of card/render-node numbering.

Apply through normal logout/login after reloading the user service manager,
not by restarting the live compositor. Revert by removing this specific drop-in,
reloading the user manager and logging out/in again. Do not put these settings
in global `/etc/environment` or session-wide environment exports.

This scopes restrictions to KWin and its children, including Xwayland. The
intended result is Intel OpenGL composition while independently launched CUDA
applications retain NVIDIA access. It neither blacklists NVIDIA nor reserves
it for VFIO. NVIDIA-connected displays would no longer be managed by KWin;
the currently connected laptop panel uses Intel.

## Source and installed-binary checks

All three variable names are present in the installed library. Matching source:

- [DRM backend](https://github.com/KDE/kwin/blob/v6.7.4/src/backends/drm/drm_backend.cpp): explicit display-device list replaces default GPU discovery.
- [GPU manager](https://github.com/KDE/kwin/blob/v6.7.4/src/core/gpumanager.cpp): explicit render-node list replaces default render-device discovery.
- [Render device](https://github.com/KDE/kwin/blob/v6.7.4/src/core/renderdevice.cpp): disabling Vulkan prevents instance creation.
- [KDE issue 521814](https://bugs.kde.org/show_bug.cgi?id=521814): documents secondary-GPU handles interfering with passthrough.

An Intel-only `VK_DRIVER_FILES` override is not the preferred proposal:
`/usr/bin/kwin_wayland` has `cap_sys_nice=ep`, and the
[Vulkan loader documentation](https://vulkan.lunarg.com/doc/view/latest/linux/LoaderDriverInterface.html)
says driver-path overrides are ignored for elevated processes. No capabilities
were removed. Disabling KWin's own Vulkan initialization avoids relying on
that loader override.

## Isolated experiments and limits

The real desktop continues reporting Intel OpenGL rendering. Four isolated KWin
runs used private D-Bus sessions, settings/runtime directories, a virtual
framebuffer and no Xwayland. They compared default settings, Intel device lists,
those lists with Vulkan disabled, and those lists with an Intel Vulkan manifest.
All initialized, but all selected NVIDIA for the virtual renderer and retained
NVIDIA handles. **These are not passing tests of the proposed desktop policy.**

The matching [virtual-backend source](https://github.com/KDE/kwin/blob/v6.7.4/src/backends/virtual/virtual_backend.cpp)
independently enumerates DRM devices and opens the first usable one, bypassing
the real DRM backend's display-device selection. These probes therefore cannot
qualify the real desktop configuration. No global restriction was added to
force this unrelated backend to pass.

The initial probe failed because its private Wayland socket path exceeded the
Unix socket limit; it was repeated using a shorter temporary path. Its failed
log is preserved. The four initialized probes required killing only their own
processes after a five-second graceful-stop timeout; clean probe shutdown is
not claimed. The original desktop compositor remained running and was checked
afterward. No probe compositor remained.

Evidence: ignored `artifacts/kwin-intel-investigation/`, including scripts,
JSON results, logs and inspected source. No driver unbind, device reset, logout,
service restart or audio-setting change occurred.

## Remaining acceptance

After an approved logout/login with this scoped configuration, verify Intel
composition and the absence of NVIDIA handles in KWin and Xwayland. Verify CUDA
access from an independently launched application. Then inspect remaining GPU
clients before VFIO assignment: Chrome, ChatGPT, Discord, Signal, Ferdium and
NVIDIA services were also observed holding handles.

This is a source-supported candidate, not proven desktop GPU release or Windows
passthrough. Production and application-test line changes: zero.
