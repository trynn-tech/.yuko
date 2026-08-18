class BaseService:
    async def health_check(self):
        return {"status": "healthy"}

    def log_event(self, message):
        print(f"Log: {message}")

# main.py
from main import BaseService

async def main():
    service = BaseService()
    health_status = await service.health_check()
    print(health_status)
    service.log_event("Service started")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
