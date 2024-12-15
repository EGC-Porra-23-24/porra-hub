from app.modules.auth.models import Community, User
from app.modules.profile.models import UserProfile
from core.seeders.BaseSeeder import BaseSeeder
from app import db


class AuthSeeder(BaseSeeder):

    priority = 1  # Higher priority

    def run(self):

        # Seeding users
        users = [
            User(email='user1@example.com', password='1234'),
            User(email='user2@example.com', password='1234'),
            User(email='user3@example.com', password='1234'),
            User(email='user4@example.com', password='1234'),
        ]

        # Inserted users with their assigned IDs are returned by `self.seed`.
        seeded_users = self.seed(users)

        # Create profiles for each user inserted.
        user_profiles = []
        names = [("John", "Doe"), ("Jane", "Doe"), ("Alice", "Smith"), ("Bob", "Johnson")]

        for user, name in zip(seeded_users, names):
            profile_data = {
                "user_id": user.id,
                "orcid": "",
                "affiliation": "Some University",
                "name": name[0],
                "surname": name[1],
            }
            user_profile = UserProfile(**profile_data)
            user_profiles.append(user_profile)

        # Seeding user profiles
        self.seed(user_profiles)


class CommunitySeeder(BaseSeeder):

    priority = 1

    def run(self):
        users = User.query.all()

        communities = [
            Community(name='Data Science Enthusiasts'),
            Community(name='AI Researchers'),
            Community(name='Python Developers'),
        ]

        seeded_communities = self.seed(communities)

        community_owners = [
            {"community_id": seeded_communities[0].id, "user_id": users[0].id},
            {"community_id": seeded_communities[1].id, "user_id": users[1].id},
        ]

        community_members = [
            {"community_id": seeded_communities[0].id, "user_id": users[0].id},
            {"community_id": seeded_communities[0].id, "user_id": users[2].id},
            {"community_id": seeded_communities[1].id, "user_id": users[1].id},
            {"community_id": seeded_communities[2].id, "user_id": users[3].id},
        ]

        community_requests = [
            {"community_id": seeded_communities[2].id, "user_id": users[0].id},
            {"community_id": seeded_communities[2].id, "user_id": users[2].id},
        ]

        for owner in community_owners:
            community = Community.query.get(owner['community_id'])
            user = User.query.get(owner['user_id'])
            community.owners.append(user)

        for member in community_members:
            community = Community.query.get(member['community_id'])
            user = User.query.get(member['user_id'])
            community.members.append(user)

        for request in community_requests:
            community = Community.query.get(request['community_id'])
            user = User.query.get(request['user_id'])
            community.requests.append(user)

        db.session.commit()
