#
# Src:
#   https://richardspowershellblog.wordpress.com/2012/09/11/finding-the-drive-letter-of-a-mounted-vhd/
#
function Get-MountedVHDDrive {
    $disks = Get-CimInstance -ClassName Win32_DiskDrive | where Caption -eq "Microsoft Virtual Disk"
    
    foreach ($disk in $disks){
        $vols = Get-CimAssociatedInstance -CimInstance $disk -ResultClassName Win32_DiskPartition
        
        foreach ($vol in $vols){
            Get-CimAssociatedInstance -CimInstance $vol -ResultClassName Win32_LogicalDisk | where VolumeName -ne 'System Reserved'
        }
    }
}
