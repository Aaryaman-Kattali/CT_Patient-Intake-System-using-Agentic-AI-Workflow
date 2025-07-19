# =============================================================================
# ADK DIAGNOSTIC TEST SCRIPT - FIXED VERSION
# =============================================================================
# This script tests all available apps on your ADK server to identify which
# ones are working and what functionality they provide.
# =============================================================================

param(
    [string]$ServerUrl = "http://127.0.0.1:8000"
)

Write-Host "ADK Diagnostic Test Script" -ForegroundColor Cyan
Write-Host "Server: $ServerUrl" -ForegroundColor White
Write-Host ""

# Utility functions
function Write-Header {
    param([string]$Message)
    Write-Host "`n=== $Message ===" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Yellow
}

function Test-AppWithMessage {
    param(
        [string]$AppName,
        [string]$TestMessage = "Hello, this is a test message"
    )
    
    Write-Header "Testing App: $AppName"
    
    $userId = "diagnostic-user"
    $sessionId = "diagnostic-session-$(Get-Date -Format 'yyyyMMddHHmmss')"
    
    try {
        # Step 1: Create session
        Write-Info "Creating session for $AppName..."
        $sessionUri = "$ServerUrl/apps/$AppName/users/$userId/sessions/$sessionId"
        
        $headers = @{
            'Content-Type' = 'application/json'
            'Accept' = 'application/json'
        }
        
        $sessionResponse = Invoke-RestMethod -Uri $sessionUri -Method POST -Body "{}" -Headers $headers -TimeoutSec 10
        Write-Success "Session created: $sessionId"
        
        # Step 2: Send message
        Write-Info "Sending test message..."
        $runBody = @{
            app_name = $AppName
            user_id = $userId
            session_id = $sessionId
            new_message = @{
                parts = @(
                    @{
                        text = $TestMessage
                    }
                )
                role = "user"
            }
        } | ConvertTo-Json -Depth 10
        
        $runResponse = Invoke-RestMethod -Uri "$ServerUrl/run" -Method POST -Body $runBody -Headers $headers -TimeoutSec 30
        
        # Step 3: Analyze response
        if ($runResponse) {
            Write-Success "App '$AppName' is working!"
            
            # Analyze response structure
            if ($runResponse -is [Array]) {
                Write-Info "Response contains $($runResponse.Count) message(s)"
                
                for ($i = 0; $i -lt $runResponse.Count; $i++) {
                    $message = $runResponse[$i]
                    Write-Info "Message $($i + 1):"
                    
                    if ($message.content -and $message.content.parts) {
                        for ($j = 0; $j -lt $message.content.parts.Count; $j++) {
                            $part = $message.content.parts[$j]
                            
                            if ($part.text) {
                                $text = $part.text
                                if ($text.Length -gt 200) {
                                    $text = $text.Substring(0, 200) + "..."
                                }
                                Write-Host "  Text: $text" -ForegroundColor White
                            }
                            
                            if ($part.functionCall) {
                                Write-Host "  Function Call: $($part.functionCall.name)" -ForegroundColor Cyan
                                if ($part.functionCall.args) {
                                    Write-Host "     Args: $($part.functionCall.args | ConvertTo-Json -Compress)" -ForegroundColor Gray
                                }
                            }
                            
                            if ($part.functionResponse) {
                                Write-Host "  Function Response: $($part.functionResponse.name)" -ForegroundColor Magenta
                                if ($part.functionResponse.response) {
                                    $responseText = $part.functionResponse.response | ConvertTo-Json -Compress
                                    if ($responseText.Length -gt 100) {
                                        $responseText = $responseText.Substring(0, 100) + "..."
                                    }
                                    Write-Host "     Response: $responseText" -ForegroundColor Gray
                                }
                            }
                        }
                    }
                    
                    if ($message.role) {
                        Write-Info "  Role: $($message.role)"
                    }
                }
            } else {
                Write-Host "  Single response: $($runResponse | ConvertTo-Json -Compress)" -ForegroundColor White
            }
            
            return @{
                Success = $true
                Response = $runResponse
                Error = $null
            }
        } else {
            Write-Error "No response received from app '$AppName'"
            return @{
                Success = $false
                Response = $null
                Error = "No response"
            }
        }
        
    }
    catch {
        Write-Error "App '$AppName' failed: $($_.Exception.Message)"
        
        if ($_.Exception.Response) {
            try {
                $errorStream = $_.Exception.Response.GetResponseStream()
                $reader = New-Object System.IO.StreamReader($errorStream)
                $errorContent = $reader.ReadToEnd()
                Write-Host "   Error details: $errorContent" -ForegroundColor Red
                $reader.Close()
                $errorStream.Close()
            }
            catch {
                Write-Host "   Could not read error details" -ForegroundColor Red
            }
        }
        
        return @{
            Success = $false
            Response = $null
            Error = $_.Exception.Message
        }
    }
}

# Main execution
Write-Header "Server Connection Test"
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $connectTask = $tcpClient.ConnectAsync("127.0.0.1", 8000)
    $connectTask.Wait(3000)
    
    if ($tcpClient.Connected) {
        Write-Success "Server is running on port 8000"
        $tcpClient.Close()
    } else {
        Write-Error "Cannot connect to server on port 8000"
        exit 1
    }
}
catch {
    Write-Error "Server connection failed: $($_.Exception.Message)"
    exit 1
}

Write-Header "Getting Available Apps"
try {
    $appsResponse = Invoke-RestMethod -Uri "$ServerUrl/list-apps" -Method GET -TimeoutSec 10
    
    if ($appsResponse -and $appsResponse.Count -gt 0) {
        Write-Success "Found $($appsResponse.Count) available apps"
        Write-Host "Apps: $($appsResponse -join ', ')" -ForegroundColor White
        
        # Test each app
        $results = @{}
        
        foreach ($app in $appsResponse) {
            $result = Test-AppWithMessage -AppName $app -TestMessage "Hello from diagnostic test. Can you help me understand what you do?"
            $results[$app] = $result
            
            Start-Sleep -Seconds 1  # Brief pause between tests
        }
        
        # Summary
        Write-Header "Diagnostic Summary"
        $workingApps = @()
        $failedApps = @()
        
        foreach ($app in $appsResponse) {
            if ($results[$app].Success) {
                $workingApps += $app
                Write-Success "$app - Working"
            } else {
                $failedApps += $app
                Write-Error "$app - Failed: $($results[$app].Error)"
            }
        }
        
        Write-Host ""
        Write-Host "Results:" -ForegroundColor Cyan
        Write-Host "  Working apps: $($workingApps.Count) / $($appsResponse.Count)" -ForegroundColor Green
        Write-Host "  Failed apps: $($failedApps.Count) / $($appsResponse.Count)" -ForegroundColor Red
        
        if ($workingApps.Count -gt 0) {
            Write-Host ""
            Write-Host "Recommended next steps:" -ForegroundColor Cyan
            Write-Host "  1. Use working apps: $($workingApps -join ', ')" -ForegroundColor White
            Write-Host "  2. Update your test scripts to use these app names" -ForegroundColor White
            Write-Host "  3. For the failed apps, check their configuration and logs" -ForegroundColor White
        }
        
    } else {
        Write-Error "No apps found on the server"
        Write-Info "You may need to configure your ADK project with agents"
    }
}
catch {
    Write-Error "Failed to get available apps: $($_.Exception.Message)"
}

Write-Host ""
Write-Host "Diagnostic completed at $(Get-Date)" -ForegroundColor Cyan