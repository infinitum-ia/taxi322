# Test script para verificar el comportamiento de consulta de dirección

$uri = "http://localhost:8000/api/v1/chat"
$body = @{
    message = "Necesito un taxi"
    thread_id = "test_ps_$(Get-Date -Format 'yyyyMMddHHmmss')"
    user_id = "test_user"
    client_id = "3022370040"
} | ConvertTo-Json

Write-Host "==================================" -ForegroundColor Cyan
Write-Host "PRUEBA DE CONSULTA DE DIRECCIÓN" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Enviando request..." -ForegroundColor Yellow
Write-Host "Client ID: 3022370040" -ForegroundColor Yellow
Write-Host ""

try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Body $body -ContentType "application/json"

    Write-Host "RESPUESTA DEL SERVIDOR:" -ForegroundColor Green
    Write-Host "----------------------" -ForegroundColor Green
    Write-Host "Thread ID: $($response.thread_id)" -ForegroundColor White
    Write-Host ""
    Write-Host "Mensaje de Alice:" -ForegroundColor White
    Write-Host $response.message -ForegroundColor White
    Write-Host ""

    if ($response.message -like "*registrada*" -or $response.message -like "*servicio antes*") {
        Write-Host "EXITO: Alice consulto la direccion registrada!" -ForegroundColor Green
    } elseif ($response.message -like "*Desde*" -or $response.message -like "*direccion*") {
        Write-Host "PROBLEMA: Alice NO consulto la direccion registrada primero" -ForegroundColor Red
    } else {
        Write-Host "Respuesta inesperada - revisar manualmente" -ForegroundColor Yellow
    }

} catch {
    Write-Host "ERROR:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
