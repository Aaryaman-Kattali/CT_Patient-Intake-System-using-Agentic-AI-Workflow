param(
    [string]$AppName = "",
    [string]$TestMessage = "",
    [string]$TargetFunction = ""
)

# SERVER CONFIGURATION - Updated to match your running server
$ServerUrl = "http://127.0.0.1:8000"

# APPLICATION CONFIGURATION
if (-not $AppName) {
    $AppName = "agent"  # Updated to use your working agent
}

# USER AND SESSION CONFIGURATION
$UserId = "test-user"
$SessionId = "test-session-$(Get-Date -Format 'yyyyMMddHHmmss')"

# MESSAGE CONFIGURATION
if (-not $TestMessage) {
    $TestMessage = "Help me with my task"
}

# RESPONSE ANALYSIS CONFIGURATION
$AnalyzeFunctionResponse = $true
if (-not $TargetFunction) {
    $TargetFunction = "collect_data"
}

# OUTPUT CONFIGURATION
$ShowFullResponse = $true
$PrettyPrint = $true

# UTILITY FUNCTIONS
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

function Test-ServerConnection {
    Write-Header "Testing Server Connection"
    
    try {
        # Test if server is running by checking if it accepts connections
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.ConnectAsync("127.0.0.1", 8000).Wait(5000)
        
        if ($tcpClient.Connected) {
            Write-Success "Server is running on port 8000"
            $tcpClient.Close()
            return $true
        } else {
            Write-Error "Cannot connect to server on port 8000"
            return $false
        }
    }
    catch {
        Write-Error "Server connection test failed: $($_.Exception.Message)"
        return $false
    }
}

function Get-AvailableEndpoints {
    Write-Header "Checking ADK API Endpoints"
    
    # Check the main endpoints we know exist
    $endpoints = @(
        "/list-apps",
        "/run", 
        "/run_sse",
        "/openapi.json"
    )
    
    $workingEndpoints = @()
    
    foreach ($endpoint in $endpoints) {
        try {
            $uri = "$ServerUrl$endpoint"
            if ($endpoint.EndsWith(".json")) {
                $response = Invoke-WebRequest -Uri $uri -Method GET -TimeoutSec 3 -ErrorAction Stop
            } else {
                # For API endpoints, just test connectivity
                $response = Invoke-WebRequest -Uri $uri -Method GET -TimeoutSec 3 -ErrorAction Stop
            }
            $workingEndpoints += @{
                Endpoint = $endpoint
                Status = $response.StatusCode
                ContentType = $response.Headers["Content-Type"]
            }
            Write-Success "Endpoint available: $endpoint (Status: $($response.StatusCode))"
        }
        catch {
            if ($_.Exception.Response.StatusCode -eq 405) {
                # Method not allowed means endpoint exists but doesn't accept GET
                Write-Success "Endpoint available: $endpoint (POST only)"
                $workingEndpoints += @{
                    Endpoint = $endpoint
                    Status = "POST only"
                    ContentType = "N/A"
                }
            } else {
                Write-Info "Endpoint check failed: $endpoint"
            }
        }
    }
    
    return $workingEndpoints
}

function Invoke-AdkRequest {
    param(
        [string]$Uri,
        [string]$Method,
        [hashtable]$Body,
        [string]$Description
    )
    
    try {
        $headers = @{
            'Content-Type' = 'application/json'
            'Accept' = 'application/json'
        }
        
        Write-Info "Making $Method request to: $Uri"
        
        if ($Body) {
            $jsonBody = $Body | ConvertTo-Json -Depth 10 -Compress
            Write-Info "Request body: $jsonBody"
            $response = Invoke-RestMethod -Uri $Uri -Method $Method -Body $jsonBody -Headers $headers -ErrorAction Stop
        } else {
            $response = Invoke-RestMethod -Uri $Uri -Method $Method -Headers $headers -ErrorAction Stop
        }
        
        Write-Success "Request successful"
        return $response
    }
    catch {
        Write-Error "Failed to $Description"
        Write-Info "Error: $($_.Exception.Message)"
        
        if ($_.Exception.Response) {
            Write-Info "Status: $($_.Exception.Response.StatusCode)"
            Write-Info "Status Description: $($_.Exception.Response.StatusDescription)"
            
            # Try to get response content for more details
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $responseContent = $reader.ReadToEnd()
                if ($responseContent) {
                    Write-Info "Response content: $responseContent"
                }
                $reader.Close()
            }
            catch {
                # Ignore if we can't read the response
            }
        }
        return $null
    }
}

function Show-Diagnostics {
    Write-Header "ADK Project Diagnostics"
    
    # Look for ADK configuration files
    $adkFiles = @(
        "adk.yaml",
        "adk.yml", 
        ".adk/config.yaml",
        ".adk/config.yml",
        "pyproject.toml"
    )
    
    Write-Info "Checking for ADK configuration files..."
    $foundConfig = $false
    
    foreach ($file in $adkFiles) {
        if (Test-Path $file) {
            Write-Success "Found configuration file: $file"
            $foundConfig = $true
        }
    }
    
    if (-not $foundConfig) {
        Write-Info "No ADK configuration files found in current directory"
        Write-Info "This might explain why multiple directories are being detected as apps"
    }
    
    # Show current directory structure
    Write-Info "Current directory: $(Get-Location)"
    Write-Info "Directory contents:"
    Get-ChildItem -Directory | ForEach-Object {
        Write-Host "  - $($_.Name)/" -ForegroundColor Gray
    }
}

# MAIN EXECUTION
Write-Header "ADK API Server Test Script (Fixed Version)"
Write-Host "App: $AppName"
Write-Host "User ID: $UserId"
Write-Host "Session ID: $SessionId"
Write-Host "Server: $ServerUrl"

# Test server connection
if (-not (Test-ServerConnection)) {
    Write-Error "Cannot proceed without server connection"
    Write-Info "Please ensure your ADK API server is running with: adk api_server"
    exit 1
}

# Discover available endpoints
$availableEndpoints = Get-AvailableEndpoints

if ($availableEndpoints.Count -eq 0) {
    Write-Error "No working endpoints found. The server might not be an ADK API server."
    Write-Info "Try checking the server documentation or running 'adk api_server --help'"
    exit 1
}

# STEP 1: Check available apps
Write-Header "Step 1: Checking Available Apps"

$listAppsUri = "$ServerUrl/list-apps"
$availableApps = Invoke-AdkRequest -Uri $listAppsUri -Method GET -Body $null -Description "list available apps"

if ($availableApps) {
    Write-Success "Available apps retrieved"
    Write-Host "Available apps: $($availableApps -join ', ')" -ForegroundColor White
    
    if ($AppName -notin $availableApps) {
        Write-Error "App '$AppName' not found in available apps"
        Write-Info "Available apps are: $($availableApps -join ', ')"
        Write-Info "Consider using one of the available apps or check your app configuration"
        # Continue anyway - the app might still work
    } else {
        Write-Success "App '$AppName' found in available apps"
    }
} else {
    Write-Info "Could not retrieve available apps, proceeding with test..."
}

# Show diagnostics if we have issues
if ($availableApps -and $availableApps.Count -gt 3) {
    Write-Info "Detected many apps ($($availableApps.Count)) - this might indicate configuration issues"
    Show-Diagnostics
}

# STEP 2: Create session first (following ADK pattern)
Write-Header "Step 2: Creating Session"

$sessionUri = "$ServerUrl/apps/$AppName/users/$UserId/sessions/$SessionId"
$sessionBody = @{}  # Empty body for session creation

$sessionResponse = Invoke-AdkRequest -Uri $sessionUri -Method POST -Body $sessionBody -Description "create session with specific ID"

$sessionCreated = $false
if ($sessionResponse) {
    Write-Success "Session created successfully"
    $sessionCreated = $true
    if ($ShowFullResponse) {
        Write-Host "Session response:"
        if ($PrettyPrint) {
            $sessionResponse | ConvertTo-Json -Depth 10 | Write-Host
        } else {
            $sessionResponse | Write-Host
        }
    }
} else {
    Write-Info "Session creation failed, but continuing with run request..."
}

# STEP 3: Send message using /run endpoint
Write-Header "Step 3: Sending Message via Run Endpoint"

$runUri = "$ServerUrl/run"
$runBody = @{
    app_name = $AppName
    user_id = $UserId
    session_id = $SessionId
    new_message = @{
        parts = @(
            @{
                text = $TestMessage
            }
        )
        role = "user"
    }
}

$response = Invoke-AdkRequest -Uri $runUri -Method POST -Body $runBody -Description "send message via run endpoint"

if ($response) {
    Write-Success "Response received via run endpoint"
    
    if ($ShowFullResponse) {
        Write-Host "Full response:"
        if ($PrettyPrint) {
            $response | ConvertTo-Json -Depth 10 | Write-Host
        } else {
            $response | Write-Host
        }
    }
} else {
    Write-Error "Failed to get response from run endpoint"
}

# RESPONSE ANALYSIS
if ($response) {
    Write-Header "Step 4: Response Analysis"
    
    # Check response structure
    Write-Info "Response type: $($response.GetType().Name)"
    
    # ADK responses are typically arrays of message objects
    $responseArray = if ($response -is [Array]) { $response } else { @($response) }
    Write-Info "Response contains $($responseArray.Count) message(s)"
    
    # Analyze each response message
    foreach ($i in 0..($responseArray.Count - 1)) {
        $message = $responseArray[$i]
        Write-Info "Analyzing message $($i + 1):"
        
        # Check for content structure
        if ($message.content) {
            Write-Success "  Found content object"
            
            if ($message.content.parts) {
                Write-Success "  Found $($message.content.parts.Count) content parts"
                
                foreach ($j in 0..($message.content.parts.Count - 1)) {
                    $part = $message.content.parts[$j]
                    Write-Info "    Part $($j + 1) type: $($part.PSObject.Properties.Name -join ', ')"
                    
                    # Check for text content
                    if ($part.text) {
                        Write-Success "    Text content found"
                        Write-Host "    Text: $($part.text)" -ForegroundColor White
                    }
                    
                    # Check for function calls
                    if ($part.functionCall) {
                        Write-Success "    Function call found: $($part.functionCall.name)"
                        if ($part.functionCall.args) {
                            Write-Host "    Function args: $($part.functionCall.args | ConvertTo-Json -Compress)" -ForegroundColor White
                        }
                    }
                    
                    # Check for function responses
                    if ($part.functionResponse) {
                        Write-Success "    Function response found: $($part.functionResponse.name)"
                        if ($part.functionResponse.response) {
                            Write-Host "    Function result: $($part.functionResponse.response | ConvertTo-Json -Compress)" -ForegroundColor White
                        }
                    }
                }
            }
        }
        
        # Check for other common ADK response fields
        if ($message.role) {
            Write-Info "  Message role: $($message.role)"
        }
        
        if ($message.author) {
            Write-Info "  Message author: $($message.author)"
        }
    }
    
    # Function-specific analysis
    if ($AnalyzeFunctionResponse -and $TargetFunction) {
        Write-Header "Function Analysis for: $TargetFunction"
        
        $functionFound = $false
        $responseString = $response | ConvertTo-Json -Depth 10
        
        if ($responseString -match $TargetFunction) {
            Write-Success "Target function '$TargetFunction' mentioned in response"
            $functionFound = $true
        }
        
        # Look for function calls and responses
        foreach ($message in $responseArray) {
            if ($message.content -and $message.content.parts) {
                foreach ($part in $message.content.parts) {
                    if ($part.functionCall -and $part.functionCall.name -eq $TargetFunction) {
                        Write-Success "Function call found: $TargetFunction"
                        Write-Host "Arguments: $($part.functionCall.args | ConvertTo-Json -Depth 3)" -ForegroundColor White
                        $functionFound = $true
                    }
                    
                    if ($part.functionResponse -and $part.functionResponse.name -eq $TargetFunction) {
                        Write-Success "Function response found: $TargetFunction"
                        Write-Host "Response: $($part.functionResponse.response | ConvertTo-Json -Depth 3)" -ForegroundColor White
                        $functionFound = $true
                    }
                }
            }
        }
        
        if (-not $functionFound) {
            Write-Info "Function '$TargetFunction' not found in response"
            Write-Info "Available functions in response:"
            foreach ($message in $responseArray) {
                if ($message.content -and $message.content.parts) {
                    foreach ($part in $message.content.parts) {
                        if ($part.functionCall) {
                            Write-Info "  - $($part.functionCall.name)"
                        }
                        if ($part.functionResponse) {
                            Write-Info "  - $($part.functionResponse.name) (response)"
                        }
                    }
                }
            }
        }
    }
    
} else {
    Write-Error "No response received from ADK API server"
}

# SUMMARY AND RECOMMENDATIONS
Write-Header "Test Summary"

if ($response) {
    Write-Success "✅ Successfully communicated with ADK API server"
    Write-Success "✅ Received response from the agent"
    if ($sessionCreated) {
        Write-Success "✅ Session management working correctly"
    }
} else {
    Write-Error "❌ Failed to get response from ADK API server"
}

Write-Header "Development Recommendations"
Write-Host "Next steps for debugging:"
Write-Host "  1. Check the ADK server logs for any error messages"
Write-Host "  2. Verify your agent configuration in the ADK project"
Write-Host "  3. Try accessing http://127.0.0.1:8000/docs for API documentation"
Write-Host "  4. Consider using the ADK CLI instead: adk run --app $AppName"
Write-Host "  5. Check if your agent requires specific initialization"

if ($availableEndpoints.Count -gt 0) {
    Write-Host "`nAvailable endpoints discovered:"
    $availableEndpoints | ForEach-Object {
        Write-Host "  - $($_.Endpoint) (Status: $($_.Status))"
    }
}

Write-Info "Test completed at $(Get-Date)"