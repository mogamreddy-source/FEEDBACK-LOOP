"""
Seed script for the Customer Feedback Platform POC.

Usage:
    cd /app/backend && python seed.py
    cd /app/backend && python seed.py --fresh   # wipes demo data first

Creates:
    - Demo owner:  demo@example.com  /  Demo1234!
    - Workspace:   ABC Restaurant (+2 locations)
    - Template:    Restaurant Experience (5 questions, published)
    - 8 realistic customer responses with ratings + comments
"""
import asyncio, os, sys, uuid, secrets, bcrypt
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "Demo1234!"

def now_offset(days_ago=0, hours_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours_ago)).isoformat()

async def seed(fresh: bool):
    if fresh:
        user = await db.users.find_one({"email": DEMO_EMAIL})
        if user:
            ws = await db.workspaces.find_one({"owner_id": user["id"]})
            if ws:
                await db.templates.delete_many({"workspace_id": ws["id"]})
                await db.responses.delete_many({"workspace_id": ws["id"]})
                await db.locations.delete_many({"workspace_id": ws["id"]})
                await db.workspace_members.delete_many({"workspace_id": ws["id"]})
                await db.workspaces.delete_one({"id": ws["id"]})
            await db.users.delete_one({"id": user["id"]})
        print("Fresh mode: cleared existing demo data.")

    if await db.users.find_one({"email": DEMO_EMAIL}):
        print(f"Demo account already exists: {DEMO_EMAIL}")
        print(f"Use password: {DEMO_PASSWORD}  (or pass --fresh to recreate)")
        return

    user_id = str(uuid.uuid4())
    await db.users.insert_one({
        "id": user_id, "full_name": "Demo Owner", "email": DEMO_EMAIL,
        "password_hash": bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode(),
        "created_at": now_offset(days_ago=7),
    })

    ws_id = str(uuid.uuid4())
    await db.workspaces.insert_one({
        "id": ws_id, "owner_id": user_id, "name": "ABC Restaurant",
        "business_type": "Restaurant", "logo_url": "", "website": "https://abc-restaurant.example",
        "location": "Hyderabad", "description": "A neighbourhood kitchen serving modern Indian plates.",
        "created_at": now_offset(days_ago=7),
    })

    loc_main = {"id": str(uuid.uuid4()), "workspace_id": ws_id, "name": "Jubilee Hills Flagship",
                "address": "Road No. 10, Jubilee Hills", "city": "Hyderabad", "phone": "+91 90000 11111",
                "created_at": now_offset(days_ago=7)}
    loc_branch = {"id": str(uuid.uuid4()), "workspace_id": ws_id, "name": "Gachibowli Branch",
                  "address": "DLF Cyber City", "city": "Hyderabad", "phone": "+91 90000 22222",
                  "created_at": now_offset(days_ago=5)}
    await db.locations.insert_many([loc_main, loc_branch])

    questions = [
        ("How would you rate your overall experience?", "rating"),
        ("How would you rate the food quality?", "rating"),
        ("How would you rate our service?", "rating"),
        ("Would you recommend us?", "yesno"),
        ("Tell us more about your experience.", "longtext"),
    ]
    qs = [{"id": str(uuid.uuid4()), "question_text": t, "question_type": qt, "required": True,
           "description": "", "options": ["Yes","No"] if qt=="yesno" else [], "sort_order": i}
          for i, (t, qt) in enumerate(questions)]
    tpl_id = str(uuid.uuid4()); slug = "abc-restaurant-experience"
    await db.templates.insert_one({
        "id": tpl_id, "workspace_id": ws_id, "name": "Restaurant Experience",
        "description": "Three-minute post-visit check-in.", "status": "PUBLISHED",
        "public_slug": slug, "published_at": now_offset(days_ago=6),
        "questions": qs, "location_id": loc_main["id"],
        "created_at": now_offset(days_ago=6), "updated_at": now_offset(days_ago=6),
    })

    reviews = [
        (5,5,5,"Yes","Absolutely wonderful. The biryani was perfect and the staff treated us like family.","positive",["food","service"]),
        (5,5,4,"Yes","Great food and friendly service, slightly slow at billing.","positive",["food","service"]),
        (4,4,4,"Yes","Lovely ambience and tasty mains. Will come back.","positive",["ambience","food"]),
        (3,3,2,"No","Food was fine but we waited 40 minutes for our order.","negative",["wait time","service"]),
        (5,5,5,"Yes","Best dinner we've had this month. Dessert menu is a treat.","positive",["food","dessert"]),
        (2,3,2,"No","Service felt rushed and the soup was cold. Please improve.","negative",["service","food"]),
        (4,5,3,"Yes","Food is clearly the hero. Service could be a bit warmer.","neutral",["food","service"]),
        (5,4,5,"Yes","Thoughtful staff and consistent flavours. Great anniversary dinner.","positive",["service","anniversary"]),
    ]
    for i, (ov, food, svc, rec, comment, sentiment, topics) in enumerate(reviews):
        answers = [
            {"id": str(uuid.uuid4()), "question_id": qs[0]["id"], "value": ov},
            {"id": str(uuid.uuid4()), "question_id": qs[1]["id"], "value": food},
            {"id": str(uuid.uuid4()), "question_id": qs[2]["id"], "value": svc},
            {"id": str(uuid.uuid4()), "question_id": qs[3]["id"], "value": rec},
            {"id": str(uuid.uuid4()), "question_id": qs[4]["id"], "value": comment},
        ]
        await db.responses.insert_one({
            "id": str(uuid.uuid4()), "workspace_id": ws_id, "template_id": tpl_id,
            "location_id": loc_main["id"] if i % 2 == 0 else loc_branch["id"],
            "submitted_at": now_offset(days_ago=5 - (i // 2), hours_ago=i * 3),
            "answers": answers,
            "ai": {"sentiment": sentiment, "confidence": 0.88, "summary": comment[:80], "topics": topics, "analyzed_at": now_offset(days_ago=5 - (i // 2))},
        })

    print("Seed complete.")
    print(f"  Login: {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print(f"  Public feedback: /f/{slug}")
    print(f"  Workspace: ABC Restaurant with 2 locations")
    print(f"  Template: Restaurant Experience (5 questions, 8 responses)")

if __name__ == "__main__":
    fresh = "--fresh" in sys.argv
    asyncio.run(seed(fresh))
