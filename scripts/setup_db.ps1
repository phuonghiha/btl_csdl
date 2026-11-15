<#
.SYNOPSIS
    Cai dat va kiem thu tron bo co so du lieu quan_ly_khach_san tu dau den cuoi.
.DESCRIPTION
    Chay lan luot:
    01_schema.sql -> 06_import_csv.sql -> 02_seed_rbac.sql -> 03_triggers.sql ->
    04_data_audit.sql -> 07_views_and_procedures.sql -> 09_seed_demo_accounts.sql ->
    10_lunar_holiday_pricing.sql -> 11_operations_procedures.sql -> 08_queries_demo_and_tests.sql
.EXAMPLE
    .\scripts\setup_db.ps1 -LoginPath btl
.EXAMPLE
    .\scripts\setup_db.ps1 -HostName 127.0.0.1 -User root
#>
param(
    [string]$MysqlExe = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    [string]$LoginPath = "",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 3306,
    [string]$User = "root",
    [switch]$SkipDemoAccounts,
    [switch]$SkipDemoQueries
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $MysqlExe)) {
    throw "Khong tim thay mysql.exe tai: $MysqlExe"
}

$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

try {
    $AuthArgs = @()
    if ($LoginPath) {
        $AuthArgs += "--login-path=$LoginPath"
    } else {
        $SecurePw = Read-Host "Nhap mat khau MySQL cho '$User@$HostName'" -AsSecureString
        $PlainPw = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePw)
        )
        $AuthArgs += @("-h", $HostName, "-P", $Port, "-u", $User, "-p$PlainPw")
    }

    Write-Host ">> Bat local_infile=1 va xoa DB cu neu can reset sach..." -ForegroundColor Cyan
    & $MysqlExe @AuthArgs --default-character-set=utf8mb4 -e "SET GLOBAL local_infile = 1; DROP DATABASE IF EXISTS quan_ly_khach_san;"
    if ($LASTEXITCODE -ne 0) { throw "Loi ket noi hoac DROP DATABASE." }

    $Files = @(
        "sql/01_schema.sql",
        "sql/06_import_csv.sql",
        "sql/02_seed_rbac.sql",
        "sql/03_triggers.sql",
        "sql/04_data_audit.sql",
        "sql/07_views_and_procedures.sql"
    )
    if (-not $SkipDemoAccounts) {
        $Files += "sql/09_seed_demo_accounts.sql"
    }
    $Files += @(
        "sql/10_lunar_holiday_pricing.sql",
        "sql/11_operations_procedures.sql",
        "sql/12_notifications_and_voucher_scope.sql"
    )
    if (-not $SkipDemoQueries) {
        $Files += "sql/08_queries_demo_and_tests.sql"
    }

    foreach ($File in $Files) {
        Write-Host ">> Dang chay $File ..." -ForegroundColor Yellow
        & $MysqlExe @AuthArgs --local-infile=1 --default-character-set=utf8mb4 --show-warnings -e "SOURCE $File;"
        if ($LASTEXITCODE -ne 0) { throw "Loi khi chay $File (exit code: $LASTEXITCODE)" }
    }

    Write-Host ">> Hoan tat cai dat va kiem thu database quan_ly_khach_san!" -ForegroundColor Green
}
finally {
    Pop-Location
}
