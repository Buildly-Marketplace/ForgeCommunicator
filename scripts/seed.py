"""Seed script to populate database with sample data."""

import asyncio
import sys
from uuid import uuid4

sys.path.insert(0, ".")

from app.db import async_session_factory, init_db
from app.models import User, Workspace, Membership, Product, Channel, ChannelMembership
from app.services.password import hash_password


async def seed_database():
    """Seed the database with sample data."""
    await init_db()
    
    async with async_session_factory() as session:
        # Check if already seeded
        from sqlalchemy import select
        existing = await session.execute(select(User).limit(1))
        if existing.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return
        
        print("Seeding database...")
        
        # Create demo users
        alice = User(
            email="alice@example.com",
            display_name="Alice Johnson",
            hashed_password=hash_password("password123"),
        )
        bob = User(
            email="bob@example.com",
            display_name="Bob Smith",
            hashed_password=hash_password("password123"),
        )
        carol = User(
            email="carol@example.com",
            display_name="Carol Williams",
            hashed_password=hash_password("password123"),
        )
        
        session.add_all([alice, bob, carol])
        await session.flush()
        print(f"Created users: {alice.email}, {bob.email}, {carol.email}")
        
        # Create workspace
        workspace = Workspace(
            name="Acme Corp",
            slug="acme-corp",
            invite_code="ACME2024",
            owner_id=alice.id,
        )
        session.add(workspace)
        await session.flush()
        print(f"Created workspace: {workspace.name}")
        
        # Add memberships
        for user, role in [(alice, "owner"), (bob, "member"), (carol, "member")]:
            membership = Membership(
                user_id=user.id,
                workspace_id=workspace.id,
                role=role,
            )
            session.add(membership)
        await session.flush()
        print("Added workspace memberships")
        
        # Create products
        products = [
            Product(
                id=uuid4(),
                workspace_id=workspace.id,
                name="Forge Communicator",
                color="#4F46E5",
            ),
            Product(
                id=uuid4(),
                workspace_id=workspace.id,
                name="Buildly Core",
                color="#10B981",
            ),
        ]
        session.add_all(products)
        await session.flush()
        print(f"Created products: {[p.name for p in products]}")
        
        # Create channels
        channels = [
            Channel(
                id=uuid4(),
                workspace_id=workspace.id,
                name="general",
                display_name="General",
                topic="Company-wide announcements and general discussion",
                is_private=False,
                created_by_id=alice.id,
            ),
            Channel(
                id=uuid4(),
                workspace_id=workspace.id,
                name="random",
                display_name="Random",
                topic="Non-work banter and water cooler conversation",
                is_private=False,
                created_by_id=alice.id,
            ),
            Channel(
                id=uuid4(),
                workspace_id=workspace.id,
                product_id=products[0].id,
                name="forge-dev",
                display_name="Forge Development",
                topic="Development discussion for Forge Communicator",
                is_private=False,
                created_by_id=alice.id,
            ),
            Channel(
                id=uuid4(),
                workspace_id=workspace.id,
                product_id=products[1].id,
                name="buildly-core",
                display_name="Buildly Core",
                topic="Buildly Core API development",
                is_private=False,
                created_by_id=bob.id,
            ),
        ]
        session.add_all(channels)
        await session.flush()
        print(f"Created channels: {[c.name for c in channels]}")
        
        # Add channel memberships
        for channel in channels:
            for user in [alice, bob, carol]:
                cm = ChannelMembership(
                    id=uuid4(),
                    user_id=user.id,
                    channel_id=channel.id,
                )
                session.add(cm)
        await session.flush()
        print("Added channel memberships")
        
        await session.commit()
        print("\n✅ Database seeded successfully!")
        print("\nDemo accounts:")
        print("  Email: alice@example.com  Password: password123 (owner)")
        print("  Email: bob@example.com    Password: password123")
        print("  Email: carol@example.com  Password: password123")
        print(f"\nWorkspace invite code: {workspace.invite_code}")


if __name__ == "__main__":
    asyncio.run(seed_database())
