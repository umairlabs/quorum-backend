from django.test import TestCase
from apps.users.models import User
from apps.assets.models import Asset, AssetCategory
from apps.purchases.models import Supplier, Purchase
from apps.ai.services import process_ai_chat, execute_ai_action, _extract_add_asset_details, _extract_purchase_details

class AIAssetCreationAndPurchaseTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            email="admin@example.com",
            password="password123",
            role="SYSTEM_ADMIN",
            first_name="Admin",
            last_name="Test"
        )
        self.cat_glasses = AssetCategory.objects.create(name="glasses")
        self.asset_pc = Asset.objects.create(
            name="PC",
            category=self.cat_glasses,
            purchase_cost=0,
            current_value=0,
            purchase_date="2026-01-01"
        )
        self.supplier = Supplier.objects.create(
            company="TechCorp",
            name="TechCorp Supplier",
            email="tech@example.com"
        )

    def test_extract_add_asset_details_exact_command(self):
        cmd = "Add an asset and the asset name is USB and the category name is Fantastic"
        a_name, c_name, c_obj, brand, model = _extract_add_asset_details(cmd, [{"id": str(self.cat_glasses.id), "name": "glasses"}])
        self.assertEqual(a_name, "USB")
        self.assertEqual(c_name, "Fantastic")

    def test_extract_add_asset_details_named_usb(self):
        cmd = "Add an asset named USB"
        a_name, c_name, c_obj, brand, model = _extract_add_asset_details(cmd, [])
        self.assertEqual(a_name, "USB")

    def test_extract_add_asset_details_create_under_category(self):
        cmd = "Create USB under category Fantastic"
        a_name, c_name, c_obj, brand, model = _extract_add_asset_details(cmd, [])
        self.assertEqual(a_name, "USB")
        self.assertEqual(c_name, "Fantastic")

    def test_extract_add_asset_details_dell_latitude_in_electronics(self):
        cmd = "Add Dell Latitude 5520 in Electronics"
        a_name, c_name, c_obj, brand, model = _extract_add_asset_details(cmd, [])
        self.assertEqual(a_name, "Dell Latitude 5520")
        self.assertEqual(c_name, "Electronics")
        self.assertEqual(brand, "Dell")
        self.assertEqual(model, "Latitude 5520")

    def test_process_ai_chat_add_asset_proposal(self):
        cmd = "Add an asset and the asset name is USB and the category name is Fantastic"
        res = process_ai_chat(self.user, cmd)
        self.assertEqual(res["intent"], "ACTION_PROPOSAL")
        action = res["action"]
        self.assertIsNotNone(action)
        self.assertEqual(action["type"], "ADD_ASSET")
        self.assertEqual(action["params"]["name"], "USB")
        self.assertEqual(action["params"]["category_name"], "Fantastic")

    def test_execute_ai_action_creates_category_and_asset(self):
        params = {
            "name": "USB",
            "category_name": "Fantastic",
            "brand": "",
            "model": ""
        }
        res = execute_ai_action(self.user, "ADD_ASSET", params)
        self.assertTrue(res["success"])
        self.assertIn("data", res)
        self.assertEqual(res["data"]["name"], "USB")
        self.assertEqual(res["data"]["category"], "Fantastic")

        # Verify DB records
        cat = AssetCategory.objects.filter(name__iexact="Fantastic").first()
        self.assertIsNotNone(cat)
        self.assertEqual(cat.name, "Fantastic")

        asset = Asset.objects.filter(name="USB").first()
        self.assertIsNotNone(asset)
        self.assertEqual(asset.category, cat)

    def test_purchase_flow_for_existing_pc_asset(self):
        cmd = "Purchase the PC asset. Quantity is 1 and the unit price is Rs. 20,000."
        res = process_ai_chat(self.user, cmd)
        self.assertEqual(res["intent"], "ACTION_PROPOSAL")
        action = res["action"]
        self.assertIsNotNone(action)
        self.assertEqual(action["type"], "CREATE_PURCHASE")
        self.assertEqual(action["params"]["asset_name"], "PC")
        self.assertEqual(action["params"]["asset_id"], str(self.asset_pc.id))
        self.assertEqual(action["params"]["quantity"], 1)
        self.assertEqual(action["params"]["unit_price"], 20000.0)

        # Execute purchase
        exec_res = execute_ai_action(self.user, "CREATE_PURCHASE", action["params"])
        self.assertTrue(exec_res["success"])
        self.assertIn("data", exec_res)
        self.assertEqual(exec_res["data"]["asset_name"], "PC")
        self.assertEqual(exec_res["data"]["quantity"], 1)
        self.assertEqual(exec_res["data"]["total_amount"], 20000.0)

        # Verify DB Purchase record
        p = Purchase.objects.filter(id=exec_res["data"]["purchase_id"]).first()
        self.assertIsNotNone(p)
        self.assertEqual(p.asset, self.asset_pc)
        self.assertEqual(p.quantity, 1)
        self.assertEqual(p.purchase_price, 20000.0)
