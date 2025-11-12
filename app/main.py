from fastapi import FastAPI
from datetime import datetime, timedelta

app = FastAPI(
    title="Magnetic Storms API",
    description="API для прогноза магнитных бурь",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"message": "API работает!", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/forecast")
async def get_forecast():
    today = datetime.now().date()
    return {
        "forecast": [
            {
                "day": "today",
                "date": today.isoformat(),
                "kp_index": 3.0,
                "storm_level": "calm"
            },
            {
                "day": "tomorrow", 
                "date": (today + timedelta(days=1)).isoformat(),
                "kp_index": 5.0,
                "storm_level": "weak"
            }
        ]
    }
