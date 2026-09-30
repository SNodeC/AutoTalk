# Local Windows GPU passthrough: prerequisite checks

Date: 29 September 2026. The owner requested a local feasibility test for
passing the laptop's NVIDIA GPU to a Windows VM. These checks establish host
prerequisites, not successful Windows GPU operation.

## Result

**The host prerequisites checked here pass. Actual GPU assignment remains
untested because the active Plasma session holds the NVIDIA device.**

| Check | Observed result |
| --- | --- |
| CPU virtualization | Opening `/dev/kvm` and creating an empty VM succeeded; KVM API version 12 |
| QEMU execution | Q35 VM with `accel=kvm`, one vCPU and 128 MiB RAM started, reported KVM enabled and guest running, and exited cleanly through QMP |
| IOMMU | NVIDIA GPU `0000:01:00.0` and its audio function `0000:01:00.1` are the only members of group 19 |
| Host display | Connected, enabled laptop panel is on Intel `0000:00:02.0`, in separate group 0; Intel is the boot VGA device |
| Interrupt remapping | Kernel reports DMAR IRQ remapping enabled in x2APIC mode |
| VFIO interface | `/dev/vfio/vfio` returned API version 0 and support for type1 and type1v2 IOMMU extensions |
| VFIO PCI driver | Matching kernel module exists; dry-run module loading resolves its dependencies |
| GPU reset | Sysfs advertises `flr bus`; no physical reset was attempted |
| Current GPU ownership | NVIDIA driver remains bound; KWin, Xwayland, desktop applications, NVIDIA services and system seat management hold relevant device handles |

An Intel-driven panel does **not** mean Plasma has released the NVIDIA GPU.
Root-readable device-client inspection confirmed that `kwin_wayland` owns both
its DRM devices and `/dev/nvidia0`. Xwayland owns its DRM card; ChatGPT, Chrome,
Discord, Signal and Ferdium also hold NVIDIA render/control handles. NVIDIA
power and persistence services have device handles too. Merely closing an
AutoTalk speech worker would not make this a safe live detach.

## QEMU smoke-test boundary

QEMU x86 was not installed. The Debian `qemu-system-x86` package
`1:11.1.1+ds-1` was downloaded and extracted locally under ignored
`artifacts/windows-gpu-preflight/qemu/`. Its shared libraries resolved against
the host. No package was installed or upgraded.

The extracted executable used the existing SeaBIOS image, no disk, no network
interface, no display and no assigned host device. QMP enabled execution,
confirmed `query-kvm` returned `enabled: true`, confirmed `query-status`
returned `running: true`, and requested a clean exit. Exit status was zero;
stderr was empty. This is a virtualization smoke test, **not a Windows boot,
PCI passthrough, GPU reset or CUDA test**.

Local evidence:

- `artifacts/windows-gpu-preflight/qemu-smoke-result.json`
- `artifacts/windows-gpu-preflight/qemu-smoke.stdout.jsonl`
- `artifacts/windows-gpu-preflight/qemu-smoke.stderr.log`

## Remaining acceptance

1. Arrange a maintenance session in which the graphical session can be ended
   if necessary. Establish a control/recovery path independent of the desktop
   before releasing GPU clients or changing driver ownership.
2. Temporarily assign both NVIDIA functions to VFIO, verify group viability,
   and exercise VM assignment and shutdown. Restore their original host drivers
   and verify Linux GPU recovery. Do not force removal while clients are active.
3. Install Windows and its NVIDIA driver, then verify device initialization,
   CUDA availability and actual AutoTalk speech synthesis.
4. Repeat VM start/stop and host reattachment to test the advertised reset path.

No GPU unbind/reset, boot configuration change, logout, service stop or audio
setting change was performed. No claim is made that passthrough, Windows driver
initialization, or reset/recovery has passed. Production and application-test
line changes: zero.

The intended ownership boundary follows the kernel's
[VFIO device and IOMMU-group documentation](https://docs.kernel.org/driver-api/vfio.html):
the device group must be available to VFIO before it can be assigned to a guest.
