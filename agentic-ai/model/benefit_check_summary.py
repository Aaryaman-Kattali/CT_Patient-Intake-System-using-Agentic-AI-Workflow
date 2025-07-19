#benefit check summary
# Enhanced Benefit Summary with Text Generation
from pydantic import BaseModel, Field
from typing import Optional, Union, Dict, Any
from datetime import date
from decimal import Decimal
from enum import Enum
import json

# ---------------------------------
# Model : CopaySummary
# ---------------------------------

class CopaySummary(BaseModel):
    """
    Simplified copay-focused benefit summary
    
    Attributes:
        client_name (str): Client's full name
        insurance_company (str): Insurance company name
        benefits_checked_on (date): Date when benefits were checked
        copay_amount (Decimal): Copay amount per visit
        is_preauthorization_required (str): Whether preauth is required (Yes/No)
        maximum_annual_cap_or_visit_limit (str): Annual cap or visit limit info
        cap_visit_limit_value (Optional[str]): Value if cap/limit exists
        other_benefit_details (Optional[str]): Additional benefit information
    """
    client_name: str
    insurance_company: str
    benefits_checked_on: date
    copay_amount: Decimal = Field(decimal_places=2)
    is_preauthorization_required: str = Field(pattern="^(Yes|No)$")
    maximum_annual_cap_or_visit_limit: str = Field(pattern="^(Yes|No)$")
    cap_visit_limit_value: Optional[str] = None
    other_benefit_details: Optional[str] = None

# ---------------------------------
# Model : DeductibleSummary
# ---------------------------------

class DeductibleSummary(BaseModel):
    """
    Detailed deductible-focused benefit summary
    
    Attributes:
        client_name (str): Client's full name
        insurance_company (str): Insurance company name
        benefits_checked_on (date): Date when benefits were checked
        deductible_individual_total (Decimal): Total individual deductible
        deductible_individual_remaining (Decimal): Remaining individual deductible
        deductible_family_total (Decimal): Total family deductible
        deductible_family_remaining (Decimal): Remaining family deductible
        coinsurance_individual_total (Decimal): Individual coinsurance percentage
        coinsurance_family_total (Decimal): Family coinsurance percentage
        out_of_pocket_maximum_individual_total (Decimal): Individual OOP max total
        out_of_pocket_maximum_individual_remaining (Decimal): Individual OOP max remaining
        out_of_pocket_maximum_family_total (Decimal): Family OOP max total
        out_of_pocket_maximum_family_remaining (Decimal): Family OOP max remaining
        is_preauthorization_required (str): Whether preauth is required (Yes/No)
        maximum_annual_cap_or_visit_limit (str): Annual cap or visit limit info
        cap_visit_limit_text (Optional[str]): Text description if cap/limit exists
        out_of_pocket_amounts_above (Optional[str]): Additional OOP information
        other_benefit_details (Optional[str]): Additional benefit information
    """
    client_name: str
    insurance_company: str
    benefits_checked_on: date
    deductible_individual_total: Decimal = Field(decimal_places=2)
    deductible_individual_remaining: Decimal = Field(decimal_places=2)
    deductible_family_total: Decimal = Field(decimal_places=2)
    deductible_family_remaining: Decimal = Field(decimal_places=2)
    coinsurance_individual_total: Decimal = Field(decimal_places=2)
    coinsurance_family_total: Decimal = Field(decimal_places=2)
    out_of_pocket_maximum_individual_total: Decimal = Field(decimal_places=2)
    out_of_pocket_maximum_individual_remaining: Decimal = Field(decimal_places=2)
    out_of_pocket_maximum_family_total: Decimal = Field(decimal_places=2)
    out_of_pocket_maximum_family_remaining: Decimal = Field(decimal_places=2)
    is_preauthorization_required: str = Field(pattern="^(Yes|No)$")
    maximum_annual_cap_or_visit_limit: str = Field(pattern="^(Yes|No)$")
    cap_visit_limit_text: Optional[str] = None
    out_of_pocket_amounts_above: Optional[str] = None
    other_benefit_details: Optional[str] = None

# ---------------------------------
# Enum for Summary Types
# ---------------------------------

class SummaryType(str, Enum):
    COPAY = "copay"
    DEDUCTIBLE = "deductible"

# ---------------------------------
# Union type for flexibility
# ---------------------------------

BenefitSummaryUnion = Union[CopaySummary, DeductibleSummary]

# ---------------------------------
# Benefit Summary Text Generator
# ---------------------------------

class BenefitSummaryTextGenerator:
    """
    Generates benefit summary text files in the exact PDF format
    Can work with either raw benefit check data or summary models
    """
    
    def __init__(self, data: Union[Dict[str, Any], BenefitSummaryUnion]):
        """
        Initialize with either:
        - Raw benefit check form data (dict)
        - CopaySummary or DeductibleSummary model
        """
        self.data = data
        self.summary_type = self._detect_summary_type()
    
    def _detect_summary_type(self) -> str:
        """Detect if data is raw form data or summary model"""
        if isinstance(self.data, (CopaySummary, DeductibleSummary)):
            return "model"
        elif isinstance(self.data, dict):
            return "raw"
        else:
            raise ValueError("Data must be either dict or summary model")
    
    def _extract_from_raw_data(self) -> Dict[str, Any]:
        """Extract summary fields from raw benefit check form data"""
        client_info = self.data.get('client_information', {})
        insurance_info = self.data.get('insurance_information', {})
        benefit_info = self.data.get('individual_family_benefit_information', {})
        benefit_details = self.data.get('benefit_details', {})
        payor_contact = self.data.get('payor_contact_information', {})
        other_details = self.data.get('other_benefit_details', {})
        
        return {
            'client_name': f"{client_info.get('child_first_name', '')} {client_info.get('child_last_name', '')}".strip(),
            'insurance_company': insurance_info.get('plan_name', ''),
            'benefits_checked_on': payor_contact.get('date_of_call', ''),
            'individual_deductible': benefit_info.get('individual_deductible', 0),
            'individual_deductible_met': benefit_info.get('individual_deductible_met', 0),
            'family_deductible': benefit_info.get('family_deductible', 0),
            'family_deductible_met': benefit_info.get('family_deductible_met', 0),
            'individual_opm': benefit_info.get('individual_opm', 0),
            'individual_opm_met': benefit_info.get('individual_opm_met', 0),
            'family_opm': benefit_info.get('family_opm', 0),
            'family_opm_met': benefit_info.get('family_opm_met', 0),
            'copay_per_visit': benefit_info.get('copay_per_visit', 0),
            'coinsurance_percentage': benefit_info.get('coinsurance_percentage', 0),
            'prior_auth_required': benefit_details.get('prior_auth_required_therapy', 'No'),
            'max_cap_exists': benefit_details.get('max_cap_exists', 'No'),
            'max_cap_amount': benefit_details.get('max_cap_amount'),
            'visit_limit_per_year': benefit_details.get('visit_limit_per_year'),
            'other_benefit_details': other_details.get('benefit_details', '')
        }
    
    def _extract_from_model(self) -> Dict[str, Any]:
        """Extract summary fields from summary model"""
        if isinstance(self.data, CopaySummary):
            return {
                'client_name': self.data.client_name,
                'insurance_company': self.data.insurance_company,
                'benefits_checked_on': self.data.benefits_checked_on,
                'copay_per_visit': self.data.copay_amount,
                'prior_auth_required': self.data.is_preauthorization_required,
                'max_cap_exists': self.data.maximum_annual_cap_or_visit_limit,
                'cap_visit_limit_value': self.data.cap_visit_limit_value,
                'other_benefit_details': self.data.other_benefit_details
            }
        elif isinstance(self.data, DeductibleSummary):
            return {
                'client_name': self.data.client_name,
                'insurance_company': self.data.insurance_company,
                'benefits_checked_on': self.data.benefits_checked_on,
                'individual_deductible': self.data.deductible_individual_total,
                'individual_deductible_met': self.data.deductible_individual_remaining,
                'family_deductible': self.data.deductible_family_total,
                'family_deductible_met': self.data.deductible_family_remaining,
                'individual_opm': self.data.out_of_pocket_maximum_individual_total,
                'individual_opm_met': self.data.out_of_pocket_maximum_individual_remaining,
                'family_opm': self.data.out_of_pocket_maximum_family_total,
                'family_opm_met': self.data.out_of_pocket_maximum_family_remaining,
                'coinsurance_percentage': self.data.coinsurance_individual_total,
                'prior_auth_required': self.data.is_preauthorization_required,
                'max_cap_exists': self.data.maximum_annual_cap_or_visit_limit,
                'cap_visit_limit_value': self.data.cap_visit_limit_text,
                'other_benefit_details': self.data.other_benefit_details
            }
    
    def generate_summary_text(self) -> str:
        """Generate the complete benefit summary text matching the PDF format"""
        
        # Extract data based on type
        if self.summary_type == "raw":
            extracted_data = self._extract_from_raw_data()
        else:
            extracted_data = self._extract_from_model()
        
        # Format date
        benefits_checked = extracted_data.get('benefits_checked_on', '')
        if isinstance(benefits_checked, date):
            benefits_checked = benefits_checked.strftime('%m/%d/%Y')
        elif isinstance(benefits_checked, str) and benefits_checked:
            try:
                benefits_checked = date.fromisoformat(benefits_checked).strftime('%m/%d/%Y')
            except:
                pass
        
        # Build the summary text
        summary_text = f"""INSURANCE BENEFIT INFORMATION
Please be aware, this is on a quote of benefits. We cannot guarantee payment or verify that definite eligibility of benefits
conveyed to us or to you by your carrier will be accurate or complete. Payment of benefits are subject to all terms, conditions,
and exclusions of the member's contract at the time of service. Initial Assessments, therapy, and reassessments do all carry a
charge, and are billed to your insurance company. Assessments can take up to 4 days, utilizing up to 2 hours a day required by
insurance companies. Although the assessment in person may take just one to two days, the full report to write, and complete
can take up to four days. The client is responsible for all "patient responsibility" deemed by the insurance company. We
suggest that you reach out to your insurance company as well and verify your benefits to ensure a full understanding of the
responsibilities the client may have.

Client Name: {extracted_data.get('client_name', 'N/A')}

Insurance Company: {extracted_data.get('insurance_company', 'N/A')}

Benefits Checked: {benefits_checked}"""

        # Add deductible information if available
        if 'individual_deductible' in extracted_data:
            summary_text += f"""

INDIVIDUAL DEDUCTIBLE: ${float(extracted_data.get('individual_deductible', 0)):,.2f}

INDIVIDUAL DEDUCTIBLE MET: ${float(extracted_data.get('individual_deductible_met', 0)):,.2f}

FAMILY DEDUCTIBLE: ${float(extracted_data.get('family_deductible', 0)):,.2f}

FAMILY DEDUCTIBLE MET: ${float(extracted_data.get('family_deductible_met', 0)):,.2f}

This is the total amount a client must pay before insurance starts paying."""

        # Add copay information
        copay_amount = extracted_data.get('copay_per_visit', 0)
        summary_text += f"""

COPAY: ${float(copay_amount):,.2f}

This amount is due at the time of each service. In most cases, copayments go toward the deductible."""

        # Add coinsurance information
        coinsurance = extracted_data.get('coinsurance_percentage', 0)
        summary_text += f"""

COINSURANCE: {float(coinsurance)}%

This is the percentage of the cost of therapy you will pay once your deductible is met until your out-of-pocket maximum is
reached."""

        # Add out-of-pocket maximum information if available
        if 'individual_opm' in extracted_data:
            summary_text += f"""

INDIVIDUAL OUT OF POCKET MAXIMUM: ${float(extracted_data.get('individual_opm', 0)):,.2f}

INDIVIDUAL OUT OF POCKET MAXIMUM MET: ${float(extracted_data.get('individual_opm_met', 0)):,.2f}

FAMILY OUT OF POCKET MAXIMUM: ${float(extracted_data.get('family_opm', 0)):,.2f}

FAMILY OUT OF POCKET MAXIMUM MET: ${float(extracted_data.get('family_opm_met', 0)):,.2f}

This is the maximum pocket expense you will incur during the benefit year. After the out-of-pocket maximum is net, a family's
insurance will pay for 100% of all medical bills for the rest of the benefit year."""

        # Add preauthorization information
        prior_auth = extracted_data.get('prior_auth_required', 'No')
        summary_text += f"""

IS PREAUTHORIZATION REQUIRED? {prior_auth}

This is a request for approval by insurance before ABA services can be started. This request can take up to a couple of weeks to
process."""

        # Add cap/limit information
        max_cap_exists = extracted_data.get('max_cap_exists', 'No')
        summary_text += f"""

IS THERE A MAXIMUM ANNUAL CAP ($) OR VISIT LIMIT: {max_cap_exists}"""

        # Add cap/limit details if they exist
        if max_cap_exists == "Yes":
            cap_value = extracted_data.get('cap_visit_limit_value') or extracted_data.get('max_cap_amount')
            visit_limit = extracted_data.get('visit_limit_per_year')
            
            if cap_value:
                try:
                    cap_amount = float(cap_value)
                    summary_text += f"\nMaximum Annual Cap: ${cap_amount:,.2f}"
                except:
                    summary_text += f"\nCap/Limit Details: {cap_value}"
            
            if visit_limit:
                summary_text += f"\nAnnual Visit Limit: {visit_limit} visits"
        
        # Add other benefit details
        other_details = extracted_data.get('other_benefit_details', '')
        if other_details:
            summary_text += f"\n\nOTHER BENEFIT DETAILS:\n{other_details}"
        
        # Add signature line
        summary_text += f"\n\nSignature of Guardian/Parent_________________________________ Date: _____________________________"
        
        return summary_text
    
    def save_to_file(self, filename: str = "benefit_summary.txt") -> str:
        """Save the benefit summary to a text file and return the filename"""
        summary_text = self.generate_summary_text()
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(summary_text)
        
        return filename
    
    def get_summary_display(self) -> Dict[str, str]:
        """Get summary for display purposes"""
        summary_text = self.generate_summary_text()
        filename = self.save_to_file()
        
        return {
            'summary_text': summary_text,
            'filename': filename,
            'status': 'generated'
        }

# ---------------------------------
# Agent-Compatible Functions
# ---------------------------------

def generate_benefit_summary_from_raw_data(benefit_check_data: Dict[str, Any], 
                                         filename: str = "benefit_summary.txt") -> Dict[str, str]:
    """
    Generate benefit summary from raw benefit check form data
    This function is designed to be called by the benefit_summary_agent
    
    Args:
        benefit_check_data: Dictionary containing raw benefit check form data
        filename: Output filename for the summary
    
    Returns:
        Dictionary with summary_text, filename, and status
    """
    generator = BenefitSummaryTextGenerator(benefit_check_data)
    return generator.get_summary_display()

def generate_benefit_summary_from_model(summary_model: BenefitSummaryUnion,
                                       filename: str = "benefit_summary.txt") -> Dict[str, str]:
    """
    Generate benefit summary from summary model
    This function is designed to be called by the benefit_summary_agent
    
    Args:
        summary_model: CopaySummary or DeductibleSummary model
        filename: Output filename for the summary
    
    Returns:
        Dictionary with summary_text, filename, and status
    """
    generator = BenefitSummaryTextGenerator(summary_model)
    return generator.get_summary_display()

# ---------------------------------
# Example Usage for Agent
# ---------------------------------

def example_agent_usage():
    """Example of how the benefit_summary_agent would use this"""
    
    # Example 1: Using raw benefit check data
    sample_raw_data = {
        'client_information': {
            'child_first_name': 'Emma',
            'child_last_name': 'Johnson'
        },
        'insurance_information': {
            'plan_name': 'Blue Cross Blue Shield Premium Plus'
        },
        'individual_family_benefit_information': {
            'individual_deductible': 1500.00,
            'individual_deductible_met': 450.00,
            'copay_per_visit': 25.00,
            'coinsurance_percentage': 20.00
        },
        'benefit_details': {
            'prior_auth_required_therapy': 'Yes',
            'max_cap_exists': 'Yes',
            'max_cap_amount': 5000.00
        },
        'payor_contact_information': {
            'date_of_call': '2024-06-15'
        },
        'other_benefit_details': {
            'benefit_details': 'ABA therapy covered. Family therapy at same rate.'
        }
    }
    
    # Generate summary
    result = generate_benefit_summary_from_raw_data(sample_raw_data)
    
    print("📋 Summary Generated!")
    print(f"📁 File: {result['filename']}")
    print(f"📝 Status: {result['status']}")
    print(f"📄 Preview:\n{result['summary_text'][:200]}...")
    
    return result

if __name__ == "__main__":
    example_agent_usage()