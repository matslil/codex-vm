# escape=`
FROM mcr.microsoft.com/windows/servercore:ltsc2022

SHELL ["powershell", "-NoLogo", "-NonInteractive", "-Command"]
COPY run.ps1 C:/environment/run.ps1
WORKDIR C:/job/workspace
ENTRYPOINT ["powershell", "-NoLogo", "-NonInteractive", "-File", "C:/environment/run.ps1"]

