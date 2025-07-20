#soap note
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal, ClassVar, Dict, Any, Union
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


# ---------------------------------
# SOAP Note Text Generator
# ---------------------------------

class SOAPNoteTextGenerator:
    """
    Generates SOAP note text files in a professional clinical format
    Can work with either raw SOAP note data or SOAPNote model
    """
    
    def __init__(self, data: Union[Dict[str, Any], SOAPNote]):
        """
        Initialize with either:
        - Raw SOAP note data (dict)
        - SOAPNote model
        """
        self.data = data
        self.data_type = self._detect_data_type()
    
    def _detect_data_type(self) -> str:
        """Detect if data is raw data or SOAPNote model"""
        if isinstance(self.data, SOAPNote):
            return "model"
        elif isinstance(self.data, dict):
            return "raw"
        else:
            raise ValueError("Data must be either dict or SOAPNote model")
    
    def _extract_from_raw_data(self) -> Dict[str, Any]:
        """Extract fields from raw SOAP note data"""
        client_info = self.data.get('client_details', {})
        soap_info = self.data.get('soap_components', {})
        insurance_info = self.data.get('insurance_information', {})
        benefit_info = self.data.get('benefit_details', {})
        intake_info = self.data.get('available_for_intake_info', {})
        pos_benefits = self.data.get('place_of_service_benefits', {})
        doc_info = self.data.get('document_information', {})
        
        return {
            'client_name': f"{client_info.get('client_first_name', '')} {client_info.get('client_last_name', '')}".strip(),
            'client_id': client_info.get('intake_client_id', ''),
            'birth_date': client_info.get('birth_date', ''),
            'subjective': soap_info.get('subjective', ''),
            'objective': soap_info.get('objective', ''),
            'assessment': soap_info.get('assessment', ''),
            'plan': soap_info.get('plan', ''),
            'insurance_plan': insurance_info.get('plan_name', ''),
            'created_by': self.data.get('created_by', ''),
            'created_at': self.data.get('created_at', ''),
            'status': intake_info.get('status', ''),
            'prior_auth_evaluation': benefit_info.get('prior_auth_required_evaluation', False),
            'prior_auth_therapy': benefit_info.get('prior_auth_required_therapy', False),
            'prior_auth_info': benefit_info.get('prior_auth_info', ''),
            'clinic_preferences': [
                client_info.get('clinic_preference_1'),
                client_info.get('clinic_preference_2'),
                client_info.get('clinic_preference_3')
            ],
            'availability': client_info.get('availability_for_sessions', ''),
            'place_of_service_covered': doc_info.get('place_of_service_covered', ''),
            'follow_up_notes': intake_info.get('follow_up_notes', '')
        }
    
    def _extract_from_model(self) -> Dict[str, Any]:
        """Extract fields from SOAPNote model"""
        return {
            'client_name': f"{self.data.client_details.client_first_name} {self.data.client_details.client_last_name}",
            'client_id': self.data.client_details.intake_client_id,
            'birth_date': self.data.client_details.birth_date,
            'subjective': self.data.soap_components.subjective,
            'objective': self.data.soap_components.objective,
            'assessment': self.data.soap_components.assessment,
            'plan': self.data.soap_components.plan,
            'insurance_plan': self.data.insurance_information.plan_name,
            'created_by': self.data.created_by,
            'created_at': self.data.created_at,
            'status': self.data.available_for_intake_info.status,
            'prior_auth_evaluation': self.data.benefit_details.prior_auth_required_evaluation,
            'prior_auth_therapy': self.data.benefit_details.prior_auth_required_therapy,
            'prior_auth_info': self.data.benefit_details.prior_auth_info,
            'clinic_preferences': [
                self.data.client_details.clinic_preference_1,
                self.data.client_details.clinic_preference_2,
                self.data.client_details.clinic_preference_3
            ],
            'availability': self.data.client_details.availability_for_sessions,
            'place_of_service_covered': self.data.document_information.place_of_service_covered,
            'follow_up_notes': self.data.available_for_intake_info.follow_up_notes
        }
    
    def generate_soap_note_text(self) -> str:
        """Generate the complete SOAP note text in professional clinical format"""
        
        # Extract data based on type
        if self.data_type == "raw":
            extracted_data = self._extract_from_raw_data()
        else:
            extracted_data = self._extract_from_model()
        
        # Format date
        created_date = extracted_data.get('created_at', '')
        if isinstance(created_date, datetime):
            created_date = created_date.strftime('%m/%d/%Y %I:%M %p')
        elif isinstance(created_date, str) and created_date:
            try:
                created_date = datetime.fromisoformat(created_date.replace('Z', '+00:00')).strftime('%m/%d/%Y %I:%M %p')
            except:
                pass
        
        # Format birth date
        birth_date = extracted_data.get('birth_date', '')
        if isinstance(birth_date, date):
            birth_date = birth_date.strftime('%m/%d/%Y')
        elif isinstance(birth_date, str) and birth_date:
            try:
                birth_date = date.fromisoformat(birth_date).strftime('%m/%d/%Y')
            except:
                pass
        
        # Build the SOAP note text
        soap_text = f"""SOAP NOTE - CLINICAL DOCUMENTATION

═══════════════════════════════════════════════════════════════════════════════

PATIENT INFORMATION
═══════════════════════════════════════════════════════════════════════════════

Patient Name: {extracted_data.get('client_name', 'N/A')}
Patient ID: {extracted_data.get('client_id', 'N/A')}
Date of Birth: {birth_date}
Insurance Plan: {extracted_data.get('insurance_plan', 'N/A')}

Date of Service: {created_date}
Clinician: {extracted_data.get('created_by', 'N/A')}
Status: {extracted_data.get('status', 'N/A')}

═══════════════════════════════════════════════════════════════════════════════

SOAP DOCUMENTATION
═══════════════════════════════════════════════════════════════════════════════

SUBJECTIVE:
{extracted_data.get('subjective', 'No subjective data recorded.')}

OBJECTIVE:
{extracted_data.get('objective', 'No objective data recorded.')}

ASSESSMENT:
{extracted_data.get('assessment', 'No assessment recorded.')}

PLAN:
{extracted_data.get('plan', 'No plan recorded.')}

═══════════════════════════════════════════════════════════════════════════════

CLIENT PREFERENCES & AVAILABILITY
═══════════════════════════════════════════════════════════════════════════════

Availability for Sessions: {extracted_data.get('availability', 'Not specified')}

Clinic Preferences:"""

        # Add clinic preferences
        preferences = extracted_data.get('clinic_preferences', [])
        for i, pref in enumerate(preferences, 1):
            if pref:
                soap_text += f"\n  {i}. {pref}"

        # Add authorization information
        soap_text += f"""

═══════════════════════════════════════════════════════════════════════════════

AUTHORIZATION & BENEFIT INFORMATION
═══════════════════════════════════════════════════════════════════════════════

Prior Authorization Required for Evaluation: {'Yes' if extracted_data.get('prior_auth_evaluation') else 'No'}
Prior Authorization Required for Therapy: {'Yes' if extracted_data.get('prior_auth_therapy') else 'No'}"""

        # Add prior auth details if available
        prior_auth_info = extracted_data.get('prior_auth_info')
        if prior_auth_info:
            soap_text += f"\nAuthorization Details: {prior_auth_info}"

        # Add place of service information
        place_of_service = extracted_data.get('place_of_service_covered')
        if place_of_service:
            soap_text += f"\nPlace of Service Covered: {place_of_service}"

        # Add follow-up notes if available
        follow_up_notes = extracted_data.get('follow_up_notes')
        if follow_up_notes:
            soap_text += f"""

═══════════════════════════════════════════════════════════════════════════════

FOLLOW-UP NOTES
═══════════════════════════════════════════════════════════════════════════════

{follow_up_notes}"""

        # Add signature section
        soap_text += f"""

═══════════════════════════════════════════════════════════════════════════════

CLINICAL SIGNATURE
═══════════════════════════════════════════════════════════════════════════════

Clinician Signature: _________________________________ Date: _____________

{extracted_data.get('created_by', 'N/A')}

═══════════════════════════════════════════════════════════════════════════════

This SOAP note has been generated in compliance with clinical documentation standards.
All information contained herein is confidential and protected under HIPAA regulations.

═══════════════════════════════════════════════════════════════════════════════"""
        
        return soap_text
    
    def save_to_file(self, filename: str = "soap_note.txt") -> str:
        """Save the SOAP note to a text file and return the filename"""
        soap_text = self.generate_soap_note_text()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(soap_text)
        
        return filename
    
    def get_soap_note_display(self) -> Dict[str, str]:
        """Get SOAP note for display purposes"""
        soap_text = self.generate_soap_note_text()
        filename = self.save_to_file()
        
        return {
            'soap_note_text': soap_text,
            'filename': filename,
            'status': 'generated'
        }


# ---------------------------------
# Agent-Compatible Functions
# ---------------------------------

def generate_soap_note_text_from_raw_data(soap_note_data: Dict[str, Any], 
                                        filename: str = "soap_note.txt") -> Dict[str, str]:
    """
    Generate SOAP note text from raw SOAP note data
    This function is designed to be called by the soap_note_agent
    
    Args:
        soap_note_data: Dictionary containing raw SOAP note data
        filename: Output filename for the SOAP note
    
    Returns:
        Dictionary with soap_note_text, filename, and status
    """
    generator = SOAPNoteTextGenerator(soap_note_data)
    return generator.get_soap_note_display()

def generate_soap_note_text_from_model(soap_note_model: SOAPNote,
                                     filename: str = "soap_note.txt") -> Dict[str, str]:
    """
    Generate SOAP note text from SOAPNote model
    This function is designed to be called by the soap_note_agent
    
    Args:
        soap_note_model: SOAPNote model
        filename: Output filename for the SOAP note
    
    Returns:
        Dictionary with soap_note_text, filename, and status
    """
    generator = SOAPNoteTextGenerator(soap_note_model)
    return generator.get_soap_note_display()


# Helper functions for creating synthetic data
def create_synthetic_soap_note(client_id: int, client_first_name: str, client_last_name: str, 
                             birth_date: date, created_by: str) -> SOAPNote:
    """Create a synthetic SOAP note with realistic data"""
    import random
    
    # Sample subjective complaints
    subjective_options = [
        "Patient reports feeling overwhelmed with work responsibilities and experiencing sleep difficulties for the past 2 weeks. States that symptoms include difficulty falling asleep, frequent waking during the night, and feeling tired during the day. Reports increased irritability and difficulty concentrating at work.",
        "Client describes persistent worry about family finances and reports physical symptoms including headaches and muscle tension. States that worrying thoughts are constant and interfere with daily activities. Reports avoiding social situations due to anxiety.",
        "Patient states they have been feeling sad and unmotivated for the past month, with decreased appetite and social withdrawal. Reports loss of interest in previously enjoyable activities and feelings of hopelessness. Denies suicidal ideation but reports feeling 'empty' most days.",
        "Client reports difficulty managing anger and frustration, particularly in interpersonal relationships. States that anger episodes are becoming more frequent and intense, leading to relationship conflicts. Reports feeling guilty after anger outbursts.",
        "Patient describes panic attacks occurring 2-3 times per week, with symptoms including rapid heartbeat, shortness of breath, sweating, and feelings of impending doom. Reports avoiding situations where panic attacks have occurred previously."
    ]
    
    # Sample objective observations
    objective_options = [
        "Patient appears well-groomed and cooperative. Maintains appropriate eye contact throughout session. Speech is clear and goal-directed with normal rate and tone. Mood appears anxious with congruent affect. Thought process is linear and organized. No evidence of perceptual disturbances or psychosis. Insight appears good.",
        "Client maintains good eye contact and appears alert and oriented x3. Speech is soft-spoken but coherent with appropriate content. Mood appears depressed with restricted affect. Psychomotor activity is slightly slowed. Thought content reveals themes of self-blame and worthlessness. No suicidal or homicidal ideation expressed.",
        "Patient appears restless and fidgety during session. Speech is rapid and pressured at times. Mood appears irritable with somewhat labile affect. Demonstrates poor frustration tolerance during interview. Thought process is tangential at times but redirects appropriately. Insight is limited regarding impact of behavior.",
        "Client appears calm and engaged throughout the session. Speech is clear, organized, and goal-directed. Mood appears stable with appropriate affect that is congruent with stated mood. Thought process is linear and logical. Demonstrates good insight into current stressors and symptoms.",
        "Patient appears tired but cooperative. Speech is slow and deliberate with increased latency of response. Mood appears dysthymic with blunted affect. Psychomotor activity is slowed. Reports decreased energy and motivation. Cognitive functioning appears intact despite slowed processing."
    ]
    
    # Sample assessments
    assessment_options = [
        "Generalized Anxiety Disorder (F41.1). Patient presents with excessive worry and physical symptoms of anxiety that significantly impair occupational and social functioning. Symptoms have persisted for over 6 months and meet criteria for GAD. Sleep disturbance and concentration difficulties are consistent with anxiety disorder.",
        "Major Depressive Disorder, single episode, moderate severity (F32.1). Patient presents with persistent depressed mood, anhedonia, sleep disturbance, and decreased appetite for duration exceeding 2 weeks. Symptoms represent significant change from previous functioning and cause clinically significant distress.",
        "Adjustment Disorder with Mixed Anxiety and Depressed Mood (F43.23). Patient's symptoms appear directly related to recent life stressors and represent maladaptive response to identifiable psychosocial stressors. Symptoms exceed normal expected response and cause significant functional impairment.",
        "Panic Disorder without Agoraphobia (F41.0). Patient experiences recurrent unexpected panic attacks with persistent concern about additional attacks. Physical symptoms during attacks include cardiorespiratory symptoms consistent with panic disorder. No evidence of agoraphobic avoidance at this time.",
        "Intermittent Explosive Disorder (F63.81). Patient demonstrates recurrent behavioral outbursts representing failure to resist aggressive impulses. Episodes are out of proportion to precipitating stressors and cause significant distress and functional impairment in relationships."
    ]
    
    # Sample plans
    plan_options = [
        "1. Initiate weekly individual psychotherapy using Cognitive Behavioral Therapy (CBT) approach to address anxiety symptoms and maladaptive thought patterns. 2. Implement relaxation techniques including progressive muscle relaxation and deep breathing exercises. 3. Develop sleep hygiene strategies to improve sleep quality. 4. Monitor symptoms weekly and reassess treatment plan in 4 weeks. 5. Consider psychiatric consultation if symptoms do not improve.",
        "1. Begin individual psychotherapy twice weekly using CBT and behavioral activation techniques. 2. Implement activity scheduling to increase engagement in pleasant activities. 3. Develop coping strategies for depressive thoughts and mood episodes. 4. Safety planning and ongoing risk assessment for suicidal ideation. 5. Follow-up appointment in 1 week with phone check-in mid-week. 6. Consider psychiatric evaluation for medication management.",
        "1. Start supportive therapy sessions weekly to process recent life changes and develop adaptive coping strategies. 2. Provide psychoeducation about adjustment disorders and normal stress responses. 3. Develop problem-solving skills to address current stressors. 4. Implement stress management techniques. 5. Reassess symptoms and functioning in 3 weeks. 6. Plan for symptom monitoring as stressors resolve.",
        "1. Begin panic disorder treatment protocol using CBT and exposure therapy techniques. 2. Teach breathing exercises and grounding techniques for acute panic episodes. 3. Implement gradual exposure therapy to previously avoided situations. 4. Psychoeducation about panic disorder and anxiety management. 5. Weekly sessions for initial 8 weeks with reassessment of progress. 6. Consider psychiatric consultation for medication evaluation.",
        "1. Initiate anger management therapy focusing on cognitive restructuring and impulse control strategies. 2. Develop trigger identification and early warning sign recognition. 3. Implement relaxation and stress management techniques. 4. Practice conflict resolution and communication skills. 5. Bi-weekly sessions initially with transition to weekly as symptoms stabilize. 6. Include family/relationship therapy as appropriate."
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
            follow_up_notes="Client has been processed through intake and is ready for treatment services. All required documentation has been completed and benefit verification is confirmed."
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
