# 1. Go to the correct directory
Write-Host "Navigating to the project directory..."
cd C:\gemini-project\vibecoding

# 2. Start Docker services in the background
Write-Host "Starting Docker services in the background..."
docker-compose up -d

# 3. Verify Docker services are running
Write-Host "Verifying Docker services..."
docker-compose ps
# Add a small pause to let services initialize
Write-Host "Pausing for 5 seconds to let services initialize..."
Start-Sleep -Seconds 5 

# 4. Start the Cloudflare tunnel in the same window
Write-Host "Starting Cloudflare tunnel... This window will now be occupied. Do not close it."
Write-Host "Look for the https://....trycloudflare.com URL in the output."
cloudflared tunnel --url http://localhost:8000
