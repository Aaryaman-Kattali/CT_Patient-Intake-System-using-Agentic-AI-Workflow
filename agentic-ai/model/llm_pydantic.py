import os
import json
from pydantic import BaseModel, EmailStr, Field, contr, model_validator
from typing import List, Literal, Annotated
from datetime import date
from uuid import UUID, uuid4

# ---------------------------------
# Type Definition
# ---------------------------------

GenderType = Literal["Male", "Female"]
YesNoType = Literal["Yes", "No"]
ServiceLocationType = Literal["Home", "Clinic", "Hospital"]
InsuranceStatusType = Literal["Primary", "Secondary", "Tertiary", "Inactive"]
AlphanumericStr = Annotated[str, Field(max_length = 10, pattern = "^[a-zA-Z0-9_]+$")]

# ---------------------------------
# Model : PatientInformation
# ---------------------------------

class PatientInformation(BaseModel):
    """
    Model has patient information

    Attributes :
        patient_first_name (str): Patient's first name.
        patient_last_name (str): Patient's last name.
        patient_gender (GenderType): Patient's gender.
        patient_dob (date): Patient's date of birth.
        patient_address (str): Patient's address.            req says alphanumeric but our defined type has a limit of 10
        patient_city (str): City of residence.
        patient_state (str): State.
        patient_pincode (int): Patient's pincode.
        patient_contact_number (int): Patient's contact number.
        patient_email (str): Patient's email address.
    """
    patient_first_name : str
    patient_last_name : str
    patient_gender : GenderType
    patient_dob : date
    patient_address : str
    patient_city : str
    patient_state : str
    patient_pincode : int
    patient_contact_number : int
    patient_email : str

# ---------------------------------
# Model : PatientSecondaryContact
# ---------------------------------

class PatientSecondaryContact(BaseModel):
    """
    Model has patient's secondary contact information

    Attributes :
        patient_parent_first_name (str): Patient's parent's first name.
        patient_parent_last_name (str): Patient's parent's last name.
        patient_emergency_contact_check (YesNoType): Checks if parent and emergency contact are same.
        patient_emergency_contact_first_name (str): Emergency contact's first name.
        patient_emergency_contact_last_name (str): Emergency contact's last name.
        patient_emergency_contact_number (int): Emergency contact's contact number.

    """
    patient_parent_first_name : str
    patient_parent_last_name : str
    patient_emergency_contact_check : YesNoType
    patient_emergency_contact_first_name : str
    patient_emergency_contact_last_name : str
    patient_emergency_contact_number : int

# ---------------------------------
# Model : PatientServicePreferences
# ---------------------------------

class ServicePreferences(BaseModel):
    """
    Model for patient's service preferences and related healthcare intake details.

    Attributes :
        service_location (ServiceLocationType): Where the patient would like to receive services.
        availability (str): Patient's availability for treatment.
        preferred_clinic (str): First preferred clinic.            picklist but how
    """
    service_location : ServiceLocationType
    availability : str
    preferred_clinic : str

# ---------------------------------
# Model : InsuranceInformation
# ---------------------------------

class InsuranceInformation(BaseModel):
    """
    Model for the patient's insurance information.

    Attributes :
        insurance_payor (str): Insurance payor.
        insurance_status (InsuranceStatusType): Insurance status.
        insurance_coverage_end_date (Optional[date]): Date when insurance coverage ends.
        insurance_card_received (YesNoType): Whether front and back of insurance card were received.
    """
    insurance_payor : str
    insurance_status : InsuranceStatusType
    insurance_coverage_end_date : date
    insurance_card_received : YesNoType

# ---------------------------------
# Model : SubscriptionInformation
# ---------------------------------

class SubscriberInformation(BaseModel):
    """
    Model for the patient's insurance information.

    Attributes :
        insurance_subscriber_first_name (str): Subscriber's first name.
        insurance_subscriber_last_name (str): Subscriber's last name.
        insurance_subscriber_dob (date): Subscriber's date of birth.
        insurance_subscriber_relation_to_patient (str): Relationship of subscriber to patient.
        insurance_subscriber_id (str): Subscriber ID.
    """
    subscriber_first_name : str
    subscriber_last_name : str
    subscriber_dob : date
    subscriber_relation_to_patient : str
    subscriber_id : AlphanumericStr

# ---------------------------------
# Model : PrimaryCareProviderInformation
# ---------------------------------

class PrimaryCareProviderInformation(BaseModel):
    """
    Model for Primary Care Provider (PCP) details.

    Attributes:
        pcp_first_name (str): PCP's first name.
        pcp_last_name (str): PCP's last name.
        pcp_phone (int): PCP's phone number.
        pcp_fax (int): PCP's fax number.
    """
    pcp_first_name : str
    pcp_last_name : str
    pcp_phone : int
    pcp_fax : int

# ---------------------------------
# Model : ReferringProviderInformation
# ---------------------------------

class ReferringProviderInformation(BaseModel):
    """
    Model for referring provider details.

    Attributes:
        referring_provider_name (str): Referring provider's full name.
        referral_received_date (date): Date when referral was received.
        practice_name (str): Name of the practice.
        referral_coordinator_name (str): Referral coordinator's name.
    """
    referring_provider_name : str
    referral_received_date : date
    practice_name : str
    referral_coordinator_name : str

# ---------------------------------
# Model : PatientHistory
# ---------------------------------

class PatientHistory(BaseModel):
    """
    Model for patient's history of illness.

    Attributes:
        patient_current_diagnosis (YesNoType) : Whether the patient has a current diagnosis.
        patient_diagnosis_age (int) : Age at which diagnosis occurred.
        patient_has_received_treatment (YesNoType) : Whether the patient has received/receives treatment.
        patient_takes_medications (YesNoType) : Whether the patient takes medications.
        patient_medications (List[str]) : List of medication names and dosages.
        patient_life_improvement_goals (List[str]) : Up to 3 improvement goals for patient over next 6 months.
    """
    patient_current_diagnosis : YesNoType
    patient_diagnosis_age : int
    patient_has_received_treatment : YesNoType
    patient_takes_medications : YesNoType
    patient_medications : List[str]
    patient_life_improvement_goals : List[str]






