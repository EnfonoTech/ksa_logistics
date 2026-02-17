# KSA Logistics - Test Data Examples for Multi-Assignment Workflow

## Overview

This document provides complete test data examples for testing the multi-assignment workflow where each Job Assignment row has its own independent workflow.

This example demonstrates a Job Record with **4 Job Assignments** (2 Own drivers, 2 External drivers).

---

## Master Data Setup

### 1. Customer

```json
{
  "doctype": "Customer",
  "customer_name": "Multi-Assignment Test Customer",
  "customer_group": "Commercial",
  "territory": "Saudi Arabia",
  "customer_type": "Company"
}
```

### 2. Shipper

```json
{
  "doctype": "Shipper",
  "shipper_name": "ABC Shipping Co.",
  "shipper_code": "ABC-001",
  "contact_person": "Ahmed Manager",
  "contact_number": "0112345678",
  "email": "contact@abcshipping.com",
  "address_line1": "Industrial Area, Block 1",
  "address_line2": "Building 5, Floor 2",
  "city": "Riyadh",
  "state": "Riyadh",
  "pincode": "12345",
  "country": "Saudi Arabia"
}
```

### 3. Consignee

```json
{
  "doctype": "Consignee",
  "consignee_name": "XYZ Trading LLC",
  "consignee_code": "XYZ-001",
  "contact_person": "Mohammed Receiver",
  "contact_number": "0123456789",
  "email": "receive@xyztrading.com",
  "address_line1": "Port Area, Warehouse 5",
  "address_line2": "Gate 3",
  "city": "Jeddah",
  "state": "Makkah",
  "pincode": "21421",
  "country": "Saudi Arabia"
}
```

### 4. Drivers (4 Drivers: 2 Own, 2 External)

```json
[
  {
    "doctype": "Driver",
    "full_name": "Ahmed Hassan",
    "cell_number": "0501234567",
    "driver_type": "Own",
    "license_number": "DL-001"
  },
  {
    "doctype": "Driver",
    "full_name": "Mohammed Ali",
    "cell_number": "0502345678",
    "driver_type": "Own",
    "license_number": "DL-002"
  },
  {
    "doctype": "Driver",
    "full_name": "Khalid Ibrahim",
    "cell_number": "0503456789",
    "driver_type": "External",
    "license_number": "DL-003",
    "transporter": "External Transport Co. 1"
  },
  {
    "doctype": "Driver",
    "full_name": "Omar Abdullah",
    "cell_number": "0504567890",
    "driver_type": "External",
    "license_number": "DL-004",
    "transporter": "External Transport Co. 2"
  }
]
```

### 5. Vehicles (4 Vehicles: 2 Internal, 2 External)

```json
[
  {
    "doctype": "Vehicle",
    "license_plate": "ABC-1234",
    "model": "Mercedes Actros",
    "vehicle_type": "Truck",
    "custom_is_external": "Internal",
    "default_driver": "Ahmed Hassan"
  },
  {
    "doctype": "Vehicle",
    "license_plate": "XYZ-5678",
    "model": "Volvo FH",
    "vehicle_type": "Truck",
    "custom_is_external": "Internal",
    "default_driver": "Mohammed Ali"
  },
  {
    "doctype": "Vehicle",
    "license_plate": "EXT-1111",
    "model": "External Truck 1",
    "vehicle_type": "Truck",
    "custom_is_external": "External"
  },
  {
    "doctype": "Vehicle",
    "license_plate": "EXT-2222",
    "model": "External Truck 2",
    "vehicle_type": "Truck",
    "custom_is_external": "External"
  }
]
```

---

## Complete Test Scenario: 4 Assignments (2 Own, 2 External)

### Job Record with 4 Assignments

```json
{
  "doctype": "Job Record",
  "date": "2026-01-28",
  "company": "Your Company",
  "customer": "Multi-Assignment Test Customer",
  "job_types": "Land Transport",
  "shipper": "ABC Shipping Co.",
  "consignee": "XYZ Trading LLC",
  "origin": "Riyadh Warehouse",
  "destination": "Jeddah Port",
  "collection_required": 1,
  "number_of_packagescontainer_pallets": "40",
  "gross_weight_kg": 2000,
  "volume_cbm": 10.0,
  "hs_description": "Electronics - Mobile Phones",
  "hs_code": "8517.12.00",
  "job_assignment": [
    {
      "driver_type": "Own",
      "driver": "Ahmed Hassan",
      "driver_name": "Ahmed Hassan",
      "driver_contact_number": "0501234567",
      "vehicle": "ABC-1234",
      "model": "Mercedes Actros",
      "number_of_packages": "10",
      "gross_weight_kg": 500,
      "volume_cbm": 2.5,
      "cargo_description": "Electronics - Mobile Phones",
      "hs_code": "8517.12.00",
      "trip_amount": 1000,
      "allowance": 200,
      "document_status": "Pending"
    },
    {
      "driver_type": "Own",
      "driver": "Mohammed Ali",
      "driver_name": "Mohammed Ali",
      "driver_contact_number": "0502345678",
      "vehicle": "XYZ-5678",
      "model": "Volvo FH",
      "number_of_packages": "10",
      "gross_weight_kg": 500,
      "volume_cbm": 2.5,
      "cargo_description": "Electronics - Mobile Phones",
      "hs_code": "8517.12.00",
      "trip_amount": 1000,
      "allowance": 200,
      "document_status": "Pending"
    },
    {
      "driver_type": "External",
      "driver": "Khalid Ibrahim",
      "driver_name": "Khalid Ibrahim",
      "driver_contact_number": "0503456789",
      "vehicle": "EXT-1111",
      "model": "External Truck 1",
      "number_of_packages": "10",
      "gross_weight_kg": 500,
      "volume_cbm": 2.5,
      "cargo_description": "Electronics - Mobile Phones",
      "hs_code": "8517.12.00",
      "trip_amount": 1200,
      "allowance": 0,
      "document_status": "Pending"
    },
    {
      "driver_type": "External",
      "driver": "Omar Abdullah",
      "driver_name": "Omar Abdullah",
      "driver_contact_number": "0504567890",
      "vehicle": "EXT-2222",
      "model": "External Truck 2",
      "number_of_packages": "10",
      "gross_weight_kg": 500,
      "volume_cbm": 2.5,
      "cargo_description": "Electronics - Mobile Phones",
      "hs_code": "8517.12.00",
      "trip_amount": 1200,
      "allowance": 0,
      "document_status": "Pending"
    }
  ]
}
```

---

## Assignment 1: Own Driver - Complete Workflow Example

### Collection Note for Assignment 1

```json
{
  "doctype": "Collection Note",
  "job_record": "JOB-00001",
  "job_assignment_name": "assignment_1_name",
  "customer": "Multi-Assignment Test Customer",
  "shipper_name": "ABC Shipping Co.",
  "collection_address": "Industrial Area, Block 1, Riyadh",
  "collection_date": "2026-01-28 10:00:00",
  "collection_status": "Completed",
  "collection_items": [
    {
      "item_description": "Package Set 1 - Electronics",
      "quantity": 5,
      "weight": 250,
      "length_cm": 50,
      "width_cm": 40,
      "height_cm": 30,
      "cbm": 0.6
    },
    {
      "item_description": "Package Set 2 - Electronics",
      "quantity": 5,
      "weight": 250,
      "length_cm": 50,
      "width_cm": 40,
      "height_cm": 30,
      "cbm": 0.6
    }
  ],
  "total_pieces": 10,
  "total_weight": 500,
  "total_cbm": 1.2,
  "cargo_description": "Electronics - Mobile Phones",
  "hs_code": "8517.12.00"
}
```

**Expected Result**: 
- Job Assignment 1: `collection_note` = "CN-00001", `collection_status` = "Completed", `document_status` = "Collection Completed"

### Waybill for Assignment 1

```json
{
  "doctype": "Waybill",
  "job_record": "JOB-00001",
  "job_assignment_name": "assignment_1_name",
  "customer": "Multi-Assignment Test Customer",
  "transport_mode": "Land",
  "waybill_number": "TWB-26-01-0001",
  "waybill_date": "2026-01-28",
  "waybill_status": "Dispatched",
  "vehicle": "ABC-1234",
  "driver": "Ahmed Hassan",
  "driver_name": "Ahmed Hassan",
  "driver_mobile": "0501234567",
  "vehicle_plate_number": "ABC-1234",
  "shipper_name": "ABC Shipping Co.",
  "consignee_name": "XYZ Trading LLC",
  "origin": "Riyadh Warehouse",
  "destination": "Jeddah Port",
  "number_of_packages": "10",
  "gross_weight": 500,
  "volume_cbm": 2.5,
  "cargo_description": "Electronics - Mobile Phones",
  "hs_code": "8517.12.00",
  "actual_dispatch_date": "2026-01-28 11:00:00"
}
```

**Expected Result**: 
- Job Assignment 1: `waybill_reference` = "WB-00001", `waybill_status` = "Dispatched", `document_status` = "Waybill Created"

### Delivery Note for Assignment 1

```json
{
  "doctype": "Delivery Note Record",
  "job_record": "JOB-00001",
  "job_assignment_name": "assignment_1_name",
  "waybill": "WB-00001",
  "customer": "Multi-Assignment Test Customer",
  "consignee_name": "XYZ Trading LLC",
  "delivery_address": "Port Area, Warehouse 5, Jeddah",
  "delivery_date": "2026-01-29",
  "delivery_time": "14:30:00",
  "delivery_status": "Delivered",
  "delivery_items": [
    {
      "item_description": "Package Set 1 - Electronics",
      "quantity": 5,
      "weight": 250,
      "length_cm": 50,
      "width_cm": 40,
      "height_cm": 30,
      "cbm": 0.6
    },
    {
      "item_description": "Package Set 2 - Electronics",
      "quantity": 5,
      "weight": 250,
      "length_cm": 50,
      "width_cm": 40,
      "height_cm": 30,
      "cbm": 0.6
    }
  ],
  "total_packages": 10,
  "total_weight": 500,
  "total_volume": 1.2,
  "receiver_name": "Ahmed Ali",
  "receiver_id": "1234567890",
  "receiver_designation": "Warehouse Manager",
  "receiver_contact": "0509876543",
  "receiver_signature": "/files/delivery_signature_1.jpg",
  "delivery_completion_time": "2026-01-29 14:35:00"
}
```

**Expected Result**: 
- Job Assignment 1: `delivery_note_record` = "DN-00001", `delivery_status` = "Delivered", `document_status` = "Delivered"

### POD for Assignment 1

```json
{
  "doctype": "Proof of Delivery",
  "job_record": "JOB-00001",
  "job_assignment_name": "assignment_1_name",
  "delivery_note": "DN-00001",
  "waybill": "WB-00001",
  "pod_date": "2026-01-29",
  "pod_status": "Verified",
  "actual_delivery_date": "2026-01-29",
  "actual_delivery_time": "14:30:00",
  "receiver_name": "Ahmed Ali",
  "receiver_id_number": "1234567890",
  "receiver_designation": "Warehouse Manager",
  "receiver_contact": "0509876543",
  "expected_packages": 10,
  "delivered_packages": 10,
  "discrepancy": 0,
  "expected_weight": 500,
  "delivered_weight": 500,
  "weight_variance": 0,
  "cargo_condition": "Good",
  "pod_remarks": "All packages delivered in good condition",
  "verified_by": "Administrator",
  "verification_date": "2026-01-29 15:00:00"
}
```

**Expected Result**: 
- Job Assignment 1: `pod_reference` = "POD-00001", `pod_status` = "Verified", `document_status` = "Completed"

---

## Assignment 2: Own Driver - Partial Workflow Example

### Collection Note for Assignment 2

```json
{
  "doctype": "Collection Note",
  "job_record": "JOB-00001",
  "job_assignment_name": "assignment_2_name",
  "collection_date": "2026-01-28 11:00:00",
  "collection_status": "Completed",
  "collection_items": [
    {
      "item_description": "Package Set 3 - Electronics",
      "quantity": 10,
      "weight": 500,
      "length_cm": 60,
      "width_cm": 50,
      "height_cm": 40,
      "cbm": 1.2
    }
  ],
  "total_pieces": 10,
  "total_weight": 500,
  "total_cbm": 1.2
}
```

### Waybill for Assignment 2

```json
{
  "doctype": "Waybill",
  "job_record": "JOB-00001",
  "job_assignment_name": "assignment_2_name",
  "transport_mode": "Land",
  "waybill_status": "In Transit",
  "vehicle": "XYZ-5678",
  "driver": "Mohammed Ali",
  "number_of_packages": "10",
  "gross_weight": 500,
  "volume_cbm": 2.5,
  "current_location": "Highway Checkpoint 1"
}
```

**Expected Result**: 
- Job Assignment 2: `waybill_reference` = "WB-00002", `waybill_status` = "In Transit", `document_status` = "In Transit"

---

## Assignment 3: External Driver - Early Stage Example

### Collection Note for Assignment 3

```json
{
  "doctype": "Collection Note",
  "job_record": "JOB-00001",
  "job_assignment_name": "assignment_3_name",
  "collection_date": "2026-01-28 12:00:00",
  "collection_status": "In Progress",
  "collection_items": [
    {
      "item_description": "Package Set 4 - Electronics",
      "quantity": 10,
      "weight": 500,
      "cbm": 1.2
    }
  ],
  "total_pieces": 10,
  "total_weight": 500
}
```

**Expected Result**: 
- Job Assignment 3: `collection_note` = "CN-00003", `collection_status` = "In Progress", `document_status` = "Collection Scheduled"

---

## Assignment 4: External Driver - Pending Example

### No documents created yet

**Expected Result**: 
- Job Assignment 4: `document_status` = "Pending"
- All workflow buttons available: "Create Collection Note"

---

## Expected Workflow States

### Assignment 1 (Own Driver - Complete)
```
Pending → Collection Scheduled → Collection Completed → 
Waybill Created → In Transit → Arrived → 
Delivered → POD Received → Completed ✅
```

### Assignment 2 (Own Driver - In Progress)
```
Pending → Collection Scheduled → Collection Completed → 
Waybill Created → In Transit → [Waiting for Arrival]
```

### Assignment 3 (External Driver - Early Stage)
```
Pending → Collection Scheduled → [Collection In Progress]
```

### Assignment 4 (External Driver - Pending)
```
Pending → [No documents created yet]
```

---

## Notes

1. **Independent Workflows**: Each assignment progresses independently. One can be completed while others are still in progress.

2. **Driver Types**: 
   - Own drivers (Ahmed Hassan, Mohammed Ali) use Internal vehicles
   - External drivers (Khalid Ibrahim, Omar Abdullah) use External vehicles

3. **Cargo Details**: Each assignment has its own cargo details (packages, weight, CBM) that flow to downstream documents.

4. **Status Tracking**: The `document_status` field in each assignment row shows the current stage of that assignment's workflow.

5. **Multiple Documents**: You can have multiple Collection Notes, Waybills, Delivery Notes, and PODs - one per assignment.

6. **Vouchers Tab**: The Vouchers tab in Job Record will show all workflow documents from all 4 assignments.

---

**Last Updated**: 2026-01-28  
**Version**: 2.0 (Multi-Assignment Workflow - 4 Assignments Example)
