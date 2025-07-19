#soap note
#soap note
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal, ClassVar
from datetime import datetime, date
from enum import Enum


class StatusEnum(str, Enum):
    DECISION_NEEDED = "Decision Needed"
    ON_HOLD = "On Hold"
    APPROVED_FOR_INTAKE = "Approved for intake"


class DocumentStatusEnum(str, Enum):
    NOT_STARTED = "Not started"
    COMPLETED = "Completed"
    ARCHIVED = "Archived"


class PlaceOfServiceBenefitEnum(str, Enum):
    COPAY = "Copay"
    COINSURANCE = "Coinsurance"
    NOT_COVERED = "Not covered"


class ClientDetails(BaseModel):
    """Client information populated from client profile"""
    intake_client_id: int = Field(..., description="System generated numeric ID from client profile")
    client_first_name: str = Field(..., description="Client's first name from profile")
    client_last_name: str = Field(..., description="Client's last name from profile")
    birth_date: date = Field(..., description="Client's birth date from profile")
    clinic_preference_1: Optional[str] = Field(None, description="Primary clinic preference")
    clinic_preference_2: Optional[str] = Field(None, description="Secondary clinic preference")
    clinic_preference_3: Optional[str] = Field(None, description="Tertiary clinic preference")
    availability_for_sessions: str = Field(..., description="Client's availability for sessions")


class AvailableForIntakeInfo(BaseModel):
    """Information about client's intake availability"""
    status: StatusEnum = Field(..., description="Current status of the client")
    hold_reason: Optional[str] = Field(None, description="Reason for putting client on hold (required if status is On Hold)")
    follow_up_notes: Optional[str] = Field(None, min_length=50, description="Follow up notes with minimum 50 characters")
    
    @field_validator('hold_reason')
    @classmethod
    def validate_hold_reason(cls, v, info):
        if info.data.get('status') == StatusEnum.ON_HOLD and not v:
            raise ValueError('Hold reason is required when status is On Hold')
        return v


class InsuranceInformation(BaseModel):
    """Insurance plan information"""
    plan_name: str = Field(..., description="Plan name selected from plan setup")


class BenefitDetails(BaseModel):
    """Benefit verification details"""
    prior_auth_required_evaluation: bool = Field(..., description="Whether prior authorization is required for evaluation")
    prior_auth_required_therapy: bool = Field(..., description="Whether prior authorization is required for therapy")
    prior_auth_info: Optional[str] = Field(None, description="Prior authorization/pre-determination information")
    has_max_cap: bool = Field(..., description="Whether there is a maximum cap")
    max_cap_amount: Optional[float] = Field(None, description="Maximum cap amount in dollars")
    visit_limit_per_year: Optional[int] = Field(None, description="Visit limit per year")
    
    @field_validator('prior_auth_info')
    @classmethod
    def validate_prior_auth_info(cls, v, info):
        if (info.data.get('prior_auth_required_evaluation') or info.data.get('prior_auth_required_therapy')) and not v:
            raise ValueError('Prior authorization information is required when prior auth is needed')
        return v
    
    @field_validator('max_cap_amount', 'visit_limit_per_year')
    @classmethod
    def validate_max_cap_fields(cls, v, info):
        if info.data.get('has_max_cap') and v is None:
            field_name = info.field_name
            raise ValueError(f'{field_name} is required when max cap is enabled')
        return v


class PlaceOfServiceBenefits(BaseModel):
    """Place of service benefit information"""
    telehealth_pos_02: PlaceOfServiceBenefitEnum = Field(..., description="Telehealth place of service benefits")
    school_pos_03: PlaceOfServiceBenefitEnum = Field(..., description="School place of service benefits")
    office_pos_11: PlaceOfServiceBenefitEnum = Field(..., description="Office place of service benefits")
    home_pos_12: PlaceOfServiceBenefitEnum = Field(..., description="Home place of service benefits")
    community_pos_99: PlaceOfServiceBenefitEnum = Field(..., description="Community place of service benefits")


class DocumentInformation(BaseModel):
    """Document status and completion information"""
    document_status: DocumentStatusEnum = Field(default=DocumentStatusEnum.NOT_STARTED, description="Current document status")
    date_time_completed: Optional[datetime] = Field(None, description="Date and time when form was completed")
    completed_by: Optional[str] = Field(None, description="User who completed the form")
    place_of_service_covered: Optional[str] = Field(None, description="Place of service covered from plan setup")
    follow_up_notes: Optional[str] = Field(None, min_length=50, description="Follow up notes with minimum 50 characters")


class SOAPComponents(BaseModel):
    """Traditional SOAP note components"""
    subjective: str = Field(..., description="Subjective information - patient's complaints, symptoms, and concerns")
    objective: str = Field(..., description="Objective information - measurable and observable data")
    assessment: str = Field(..., description="Assessment - clinical impression and diagnosis")
    plan: str = Field(..., description="Plan - treatment plan and next steps")


class SOAPNote(BaseModel):
    """Complete SOAP Note model with all components"""
    # Core SOAP components
    soap_components: SOAPComponents = Field(..., description="Traditional SOAP note components")
    
    # Client and intake information
    client_details: ClientDetails = Field(..., description="Client information from profile")
    available_for_intake_info: AvailableForIntakeInfo = Field(..., description="Intake availability information")
    
    # Insurance and benefit information
    insurance_information: InsuranceInformation = Field(..., description="Insurance plan information")
    benefit_details: BenefitDetails = Field(..., description="Benefit verification details")
    place_of_service_benefits: PlaceOfServiceBenefits = Field(..., description="Place of service benefit information")
    
    # Document tracking
    document_information: DocumentInformation = Field(..., description="Document status and completion tracking")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now, description="When the SOAP note was created")
    updated_at: Optional[datetime] = Field(None, description="When the SOAP note was last updated")
    created_by: str = Field(..., description="User who created the SOAP note")
    
    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
    }
    
    # Fix for Pydantic v2: Use ClassVar to mark non-field class attributes
    model_json_schema_extra: ClassVar[dict] = {
        "example": {
            "soap_components": {
                "subjective": "Patient reports experiencing anxiety and difficulty concentrating for the past 3 weeks. States that symptoms worsen during work hours and affect daily functioning.",
                "objective": "Patient appears alert and cooperative. Speech is clear and coherent. Mood appears anxious with appropriate affect. No signs of psychosis or suicidal ideation.",
                "assessment": "Generalized Anxiety Disorder (F41.1). Patient presents with classic symptoms of anxiety affecting occupational functioning.",
                "plan": "1. Begin cognitive behavioral therapy sessions twice weekly. 2. Psychoeducation about anxiety management techniques. 3. Monitor symptoms and reassess in 2 weeks."
            },
            "client_details": {
                "intake_client_id": 12345,
                "client_first_name": "John",
                "client_last_name": "Doe",
                "birth_date": "1985-03-15",
                "clinic_preference_1": "Downtown Clinic",
                "clinic_preference_2": "Northside Clinic",
                "clinic_preference_3": "Westside Clinic",
                "availability_for_sessions": "Weekdays 9 AM - 5 PM"
            },
            "available_for_intake_info": {
                "status": "Approved for intake",
                "follow_up_notes": "Client has been approved for intake and is ready to begin treatment. Initial assessment completed successfully."
            },
            "insurance_information": {
                "plan_name": "Blue Cross Blue Shield Standard"
            },
            "benefit_details": {
                "prior_auth_required_evaluation": True,
                "prior_auth_required_therapy": True,
                "prior_auth_info": "Prior authorization approved for 12 sessions, reference number: PA123456789",
                "has_max_cap": True,
                "max_cap_amount": 2000.00,
                "visit_limit_per_year": 20
            },
            "place_of_service_benefits": {
                "telehealth_pos_02": "Copay",
                "school_pos_03": "Not covered",
                "office_pos_11": "Copay",
                "home_pos_12": "Coinsurance",
                "community_pos_99": "Not covered"
            },
            "document_information": {
                "document_status": "Completed",
                "date_time_completed": "2025-07-07T10:30:00",
                "completed_by": "Dr. Smith",
                "place_of_service_covered": "Office, Telehealth",
                "follow_up_notes": "Benefit verification completed successfully. All required authorizations are in place for treatment to begin."
            },
            "created_by": "Dr. Smith"
        }
    }


# Helper functions for creating synthetic data
def create_synthetic_soap_note(client_id: int, client_first_name: str, client_last_name: str, 
                             birth_date: date, created_by: str) -> SOAPNote:
    """Create a synthetic SOAP note with realistic data"""
    import random
    
    # Sample subjective complaints
    subjective_options = [
        "Patient reports feeling overwhelmed with work responsibilities and experiencing sleep difficulties for the past 2 weeks.",
        "Client describes persistent worry about family finances and reports physical symptoms including headaches and muscle tension.",
        "Patient states they have been feeling sad and unmotivated for the past month, with decreased appetite and social withdrawal.",
        "Client reports difficulty managing anger and frustration, particularly in interpersonal relationships.",
        "Patient describes panic attacks occurring 2-3 times per week, with symptoms including rapid heartbeat and shortness of breath."
    ]
    
    # Sample objective observations
    objective_options = [
        "Patient appears well-groomed and cooperative. Speech is clear and goal-directed. Mood appears anxious with congruent affect.",
        "Client maintains good eye contact and appears alert. Speech is soft-spoken but coherent. Mood appears depressed with restricted affect.",
        "Patient appears restless and fidgety. Speech is rapid and pressured. Mood appears irritable with labile affect.",
        "Client appears calm and engaged. Speech is clear and organized. Mood appears stable with appropriate affect.",
        "Patient appears tired but cooperative. Speech is slow and deliberate. Mood appears dysthymic with blunted affect."
    ]
    
    # Sample assessments
    assessment_options = [
        "Generalized Anxiety Disorder (F41.1). Patient presents with classic symptoms of anxiety affecting occupational and social functioning.",
        "Major Depressive Disorder, single episode, moderate severity (F32.1). Symptoms consistent with clinical depression.",
        "Adjustment Disorder with Mixed Anxiety and Depressed Mood (F43.23). Symptoms related to recent life stressors.",
        "Panic Disorder without Agoraphobia (F41.0). Recurrent panic attacks with anticipatory anxiety.",
        "Intermittent Explosive Disorder (F63.81). Difficulty with anger management and impulse control."
    ]
    
    # Sample plans
    plan_options = [
        "1. Begin weekly cognitive behavioral therapy sessions. 2. Implement relaxation techniques and stress management strategies. 3. Monitor symptoms and reassess in 4 weeks.",
        "1. Initiate individual psychotherapy twice weekly. 2. Develop coping strategies for depressive symptoms. 3. Safety planning and risk assessment. 4. Follow-up in 2 weeks.",
        "1. Start supportive therapy sessions. 2. Psychoeducation about adjustment disorders. 3. Develop healthy coping mechanisms. 4. Reassess in 3 weeks.",
        "1. Begin panic disorder treatment protocol. 2. Breathing exercises and grounding techniques. 3. Gradual exposure therapy. 4. Weekly sessions for 8 weeks.",
        "1. Anger management therapy sessions. 2. Cognitive restructuring techniques. 3. Impulse control strategies. 4. Bi-weekly sessions initially."
    ]
    
    synthetic_note = SOAPNote(
        soap_components=SOAPComponents(
            subjective=random.choice(subjective_options),
            objective=random.choice(objective_options),
            assessment=random.choice(assessment_options),
            plan=random.choice(plan_options)
        ),
        client_details=ClientDetails(
            intake_client_id=client_id,
            client_first_name=client_first_name,
            client_last_name=client_last_name,
            birth_date=birth_date,
            clinic_preference_1=random.choice(["Downtown Clinic", "Northside Clinic", "Westside Clinic", "Eastside Clinic"]),
            clinic_preference_2=random.choice(["Community Health Center", "Wellness Center", "Mental Health Clinic"]),
            clinic_preference_3=random.choice(["Telehealth Services", "Mobile Clinic", "University Clinic"]),
            availability_for_sessions=random.choice([
                "Weekdays 9 AM - 5 PM",
                "Evenings after 6 PM",
                "Weekends only",
                "Flexible scheduling",
                "Mornings before 11 AM"
            ])
        ),
        available_for_intake_info=AvailableForIntakeInfo(
            status=random.choice(list(StatusEnum)),
            follow_up_notes="Client has been processed through intake and is ready for treatment services. All required documentation has been completed."
        ),
        insurance_information=InsuranceInformation(
            plan_name=random.choice([
                "Blue Cross Blue Shield Standard",
                "Aetna Better Health",
                "UnitedHealthcare Community Plan",
                "Medicaid Managed Care",
                "Cigna HealthSpring"
            ])
        ),
        benefit_details=BenefitDetails(
            prior_auth_required_evaluation=random.choice([True, False]),
            prior_auth_required_therapy=random.choice([True, False]),
            prior_auth_info=f"Prior authorization approved for {random.randint(8, 20)} sessions, reference number: PA{random.randint(100000000, 999999999)}",
            has_max_cap=random.choice([True, False]),
            max_cap_amount=random.choice([1500.00, 2000.00, 2500.00, 3000.00]),
            visit_limit_per_year=random.randint(12, 30)
        ),
        place_of_service_benefits=PlaceOfServiceBenefits(
            telehealth_pos_02=random.choice(list(PlaceOfServiceBenefitEnum)),
            school_pos_03=random.choice(list(PlaceOfServiceBenefitEnum)),
            office_pos_11=random.choice(list(PlaceOfServiceBenefitEnum)),
            home_pos_12=random.choice(list(PlaceOfServiceBenefitEnum)),
            community_pos_99=random.choice(list(PlaceOfServiceBenefitEnum))
        ),
        document_information=DocumentInformation(
            document_status=DocumentStatusEnum.COMPLETED,
            date_time_completed=datetime.now(),
            completed_by=created_by,
            place_of_service_covered=random.choice([
                "Office, Telehealth",
                "Office, Home, Community",
                "Telehealth only",
                "Office, School, Community",
                "All locations covered"
            ]),
            follow_up_notes="Benefit verification completed successfully. All required authorizations are in place for treatment to begin as scheduled."
        ),
        created_by=created_by
    )
    
    return synthetic_note