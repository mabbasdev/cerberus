import wmi
c = wmi.WMI()

print("=== ALL PHYSICAL DISKS ===")
for disk in c.Win32_DiskDrive():
    print(f"DeviceID: {disk.DeviceID}")
    print(f"  Model:          {disk.Model}")
    print(f"  InterfaceType:  {disk.InterfaceType}")
    print(f"  SerialNumber:   {disk.SerialNumber}")
    print(f"  Size:           {disk.Size}")
    print()

print("=== ALL LOGICAL DISKS ===")
for ld in c.Win32_LogicalDisk():
    print(f"DeviceID: {ld.DeviceID}  DriveType: {ld.DriveType}  VolumeName: {ld.VolumeName}")
print()

print("=== ASSOCIATIONS FOR E: ===")
for ld in c.Win32_LogicalDisk():
    if ld.DeviceID == "E:":
        print(f"E: found")
        for part in ld.associators(
            wmi_association_class="Win32_LogicalDiskToPartition",
            wmi_result_class="Win32_DiskPartition",
        ):
            print(f"  Partition: {part.DeviceID}")
            for disk in part.associators(
                wmi_association_class="Win32_DiskDriveToDiskPartition",
                wmi_result_class="Win32_DiskDrive",
            ):
                print(f"    Disk:          {disk.DeviceID}")
                print(f"    Model:         {disk.Model}")
                print(f"    InterfaceType: {disk.InterfaceType}")
                print(f"    SerialNumber:  {disk.SerialNumber}")