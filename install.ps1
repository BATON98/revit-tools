# Установка / обновление RevitTools. Запуск: PowerShell -> вставить содержимое файла -> Enter.
$ErrorActionPreference = 'Stop'
$branch = 'pyrevit-tools'
$dest = 'C:\RevitTools'
$zip = Join-Path $env:TEMP 'revit-tools.zip'
$tmp = Join-Path $env:TEMP 'revit-tools-unzip'

Write-Host 'Скачиваю RevitTools с GitHub...'
Invoke-WebRequest "https://github.com/BATON98/revit-tools/archive/refs/heads/$branch.zip" -OutFile $zip
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive $zip $tmp

New-Item -ItemType Directory -Force $dest | Out-Null
Remove-Item (Join-Path $dest 'RevitTools.extension') -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $tmp "revit-tools-$branch\*") $dest -Recurse -Force
Remove-Item $zip, $tmp -Recurse -Force

if (Get-Command pyrevit -ErrorAction SilentlyContinue) {
    pyrevit extensions paths add $dest
    Write-Host "Готово. Папка $dest подключена к pyRevit. В Revit нажмите pyRevit -> Reload." -ForegroundColor Green
} else {
    Write-Host "Файлы скопированы в $dest." -ForegroundColor Green
    Write-Host "Команда pyrevit не найдена: добавьте папку вручную — pyRevit -> Settings -> Custom Extension Directories -> Add folder -> $dest -> Save Settings and Reload." -ForegroundColor Yellow
}
