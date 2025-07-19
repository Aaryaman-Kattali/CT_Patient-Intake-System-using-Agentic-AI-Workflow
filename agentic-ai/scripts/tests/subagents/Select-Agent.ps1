# =============================================================================
# AGENT SELECTION HELPER SCRIPT (PowerShell Version) - UPDATED
# =============================================================================
# Updated to work with your actual agent structure
# =============================================================================

param(
    [string]$AgentName = ""
)

# Base directory (assuming script is in scripts/tests/subagents/)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TestScript = Join-Path $ScriptDir "Test-AdkApp.ps1"

# Check if the main test script exists
if (-not (Test-Path $TestScript)) {
    Write-Host "❌ Main test script not found at: $TestScript" -ForegroundColor Red
    Write-Host "Please ensure Test-AdkApp.ps1 is in the same directory" -ForegroundColor Yellow
    exit 1
}

# Function to run test with specific configuration
function Invoke-AgentTest {
    param(
        [string]$AppName,
        [string]$TestMessage,
        [string]$FunctionName,
        [string]$Description
    )
    
    Write-Host "🚀 Testing: $Description" -ForegroundColor Cyan
    Write-Host "App: $AppName" -ForegroundColor White
    Write-Host "Message: $TestMessage" -ForegroundColor White
    Write-Host ""
    
    # Run the test script with parameters
    & $TestScript -AppName $AppName -TestMessage $TestMessage -TargetFunction $FunctionName
}

# Function to show interactive menu
function Show-Menu {
    do {
        Write-Host ""
        Write-Host "=== Agent Test Menu ===" -ForegroundColor Cyan
        Write-Host "1. Main Agent (root coordinator)" -ForegroundColor White
        Write-Host "2. Data Collector Subagent" -ForegroundColor White
        Write-Host "3. Email Subagent" -ForegroundColor White
        Write-Host "4. Custom (enter your own configuration)" -ForegroundColor White
        Write-Host "5. Exit" -ForegroundColor White
        Write-Host ""
        
        $choice = Read-Host "Select an option (1-5)"
        
        switch ($choice) {
            "1" { Test-MainAgent; break }
            "2" { Test-DataCollector; break }
            "3" { Test-EmailAgent; break }
            "4" { Test-Custom; break }
            "5" { Write-Host "Goodbye!" -ForegroundColor Green; exit 0 }
            default { 
                Write-Host "Invalid option. Please try again." -ForegroundColor Red
                continue
            }
        }
    } while ($true)
}

# Updated test configurations for your actual agent structure
function Test-MainAgent {
    Invoke-AgentTest -AppName "agent" `
                     -TestMessage "Hello, I'm a new patient inquiry. Can you help me with the intake process?" `
                     -FunctionName "delegate_task" `
                     -Description "Main Agent (Patient Intake Coordinator)"
}

function Test-DataCollector {
    # Try to test subagent functionality through the main agent
    Invoke-AgentTest -AppName "agent" `
                     -TestMessage "I need to collect some patient data. Can you help me gather the required information for a new patient intake?" `
                     -FunctionName "collect_data" `
                     -Description "Data Collection via Main Agent"
}

function Test-EmailAgent {
    # Try to test email functionality through the main agent
    Invoke-AgentTest -AppName "agent" `
                     -TestMessage "I need to send a confirmation email to a patient. Can you help me with that?" `
                     -FunctionName "send_email" `
                     -Description "Email Functionality via Main Agent"
}

function Test-Custom {
    Write-Host "=== Custom Agent Configuration ===" -ForegroundColor Cyan
    $customApp = Read-Host "Enter app name (use 'agent' for your main app)"
    $customMessage = Read-Host "Enter test message"
    $customFunction = Read-Host "Enter function name to analyze (optional, press Enter to skip)"
    
    if ([string]::IsNullOrWhiteSpace($customFunction)) {
        $customFunction = "custom_function"
    }
    
    Invoke-AgentTest -AppName $customApp `
                     -TestMessage $customMessage `
                     -FunctionName $customFunction `
                     -Description "Custom Agent Configuration"
}

function Show-Help {
    Write-Host "Usage: .\Select-Agent.ps1 [agent_name]" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Available agent names:" -ForegroundColor White
    Write-Host "  main, agent         - Test the main agent" -ForegroundColor Gray
    Write-Host "  data, collector     - Test data collection via main agent" -ForegroundColor Gray
    Write-Host "  email, mail         - Test email functionality via main agent" -ForegroundColor Gray
    Write-Host "  custom              - Enter custom configuration" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Note: Your agent structure uses 'agent' as the main app name." -ForegroundColor Yellow
    Write-Host "Subagents are tested through the main agent." -ForegroundColor Yellow
}

# Main execution logic
switch ($AgentName.ToLower()) {
    { $_ -in @("main", "agent", "root") } {
        Test-MainAgent
    }
    { $_ -in @("data", "data_collector", "collector") } {
        Test-DataCollector
    }
    { $_ -in @("email", "mail") } {
        Test-EmailAgent
    }
    "custom" {
        Test-Custom
    }
    { $_ -in @("help", "-h", "--help", "?") } {
        Show-Help
    }
    "" {
        Show-Menu
    }
    default {
        Write-Host "Unknown agent: $AgentName" -ForegroundColor Red
        Write-Host "Use '.\Select-Agent.ps1 help' to see available options" -ForegroundColor Yellow
        exit 1
    }
}