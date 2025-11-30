"""
Text parsing service for extracting structured data from OCR text
Supports hybrid approach: regex first, Gemini LLM fallback for low confidence
"""
import re
import os
from typing import Dict, List, Optional, Tuple
from services.confidence import ConfidenceCalculator

class TextParser:
    """Parse OCR text to extract structured contact information"""
    
    # Expected fields
    ALL_FIELDS = ['name', 'organisation', 'mobile_number', 'landline_number', 'email_id', 'designation']
    
    def __init__(self, use_llm_fallback=True, llm_confidence_threshold=0.95):
        """
        Initialize parser
        
        Args:
            use_llm_fallback: If True, use Gemini LLM when regex confidence is low
            llm_confidence_threshold: Confidence threshold below which to use LLM (default: 0.95)
        """
        self.confidence_calc = ConfidenceCalculator()
        # Ensure use_llm_fallback is boolean and API key exists
        api_key = os.getenv('GEMINI_API_KEY')
        self.use_llm_fallback = bool(use_llm_fallback) and bool(api_key)
        self.llm_confidence_threshold = float(llm_confidence_threshold)
        
        # Lazy load Gemini parser (only if needed)
        self._gemini_parser = None
    
    def parse(self, text: str) -> Dict:
        """
        Parse text and extract contact fields with confidence scores
        
        Args:
            text: Raw OCR text
            
        Returns:
            dict: {
                'extracted_data': {
                    'field_name': {
                        'value': str,
                        'confidence': float,
                        'source': str
                    }
                },
                'overall_confidence': float,
                'parsing_metadata': {
                    'total_lines': int,
                    'detected_fields': list,
                    'missing_fields': list,
                    'extraction_method': str
                }
            }
        """
        if not text or not text.strip():
            return self._empty_result()
        
        # Normalize text
        lines = self._split_into_lines(text)
        
        # Extract fields
        extracted = {}
        
        # Extract email (most reliable)
        email_result = self._extract_email(text, lines)
        if email_result:
            extracted['email_id'] = email_result
        
        # Extract phone numbers
        phone_results = self._extract_phones(text, lines)
        if phone_results.get('mobile_number'):
            extracted['mobile_number'] = phone_results['mobile_number']
        if phone_results.get('landline_number'):
            extracted['landline_number'] = phone_results['landline_number']
        
        # Extract name
        name_result = self._extract_name(text, lines)
        if name_result:
            extracted['name'] = name_result
        
        # Extract organisation
        org_result = self._extract_organisation(text, lines)
        if org_result:
            extracted['organisation'] = org_result
        
        # Extract designation
        designation_result = self._extract_designation(text, lines)
        if designation_result:
            extracted['designation'] = designation_result
        
        # Calculate overall confidence
        field_confidences = {
            field: data['confidence']
            for field, data in extracted.items()
        }
        overall_confidence = self.confidence_calc.calculate_overall_confidence(field_confidences)
        
        # Get detected and missing fields
        detected_fields = self.confidence_calc.get_detected_fields(field_confidences)
        missing_fields = self.confidence_calc.get_missing_fields(field_confidences, self.ALL_FIELDS)
        
        regex_result = {
            'extracted_data': extracted,
            'overall_confidence': overall_confidence,
            'raw_text': text,
            'parsing_metadata': {
                'total_lines': len(lines),
                'detected_fields': detected_fields,
                'missing_fields': missing_fields,
                'extraction_method': 'rule_based'
            }
        }
        
        # Hybrid approach: Use LLM if confidence is low or critical fields missing
        if self.use_llm_fallback and self._should_use_llm(regex_result):
            llm_result = self._parse_with_llm(text)
            if llm_result:
                # Always use LLM result when confidence is below threshold (LLM handles OCR issues better)
                if overall_confidence < self.llm_confidence_threshold:
                    # For low confidence, prefer LLM results (better at handling OCR spacing issues)
                    return self._merge_results(regex_result, llm_result, prefer_llm=True)
                else:
                    # For high confidence, merge intelligently
                    return self._merge_results(regex_result, llm_result, prefer_llm=False)
        
        return regex_result
    
    def _should_use_llm(self, regex_result: Dict) -> bool:
        """Determine if LLM should be used based on regex results"""
        overall_conf = regex_result.get('overall_confidence', 0)
        extracted = regex_result.get('extracted_data', {})
        raw_text = regex_result.get('raw_text', '')
        
        # Use LLM if:
        # 1. Overall confidence below threshold
        if overall_conf < self.llm_confidence_threshold:
            return True
        
        # 2. Critical fields missing (name, email, or mobile)
        critical_fields = ['name', 'email_id', 'mobile_number']
        missing_critical = [f for f in critical_fields if f not in extracted]
        if len(missing_critical) >= 2:  # Missing 2+ critical fields
            return True
        
        # 3. Low confidence on critical fields
        for field in critical_fields:
            if field in extracted:
                field_conf = extracted[field].get('confidence', 0)
                if field_conf < 0.80:  # Low confidence on critical field
                    return True
        
        # 4. Email extraction issues - check if email might be incomplete due to OCR spacing
        # If we see patterns like "name surname@domain" or "@domain" with name nearby, use LLM
        if 'email_id' in extracted:
            email_value = extracted['email_id'].get('value', '')
            # Check if email looks incomplete (short name part) and there's a name nearby
            if email_value and '@' in email_value:
                email_name_part = email_value.split('@')[0]
                # If email name part is very short (1-2 words) but we see longer name in text
                if len(email_name_part.split('.')) <= 2:
                    # Check if there's a name pattern before the email in text
                    name_before_email = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+[a-z]+@', raw_text, re.IGNORECASE)
                    if name_before_email:
                        return True  # Likely OCR spacing issue, use LLM
        
        return False
    
    def _parse_with_llm(self, text: str) -> Optional[Dict]:
        """Parse using Gemini LLM"""
        if not self._gemini_parser:
            try:
                from services.gemini_parser import GeminiParser
                self._gemini_parser = GeminiParser()
            except Exception as e:
                print(f"Failed to initialize Gemini parser: {str(e)}")
                return None
        
        return self._gemini_parser.parse(text)
    
    def _merge_results(self, regex_result: Dict, llm_result: Dict, prefer_llm: bool = False) -> Dict:
        """Merge regex and LLM results, preferring higher confidence or LLM when specified"""
        regex_data = regex_result.get('extracted_data', {})
        llm_data = llm_result.get('extracted_data', {})
        
        merged = {}
        
        # For each field, choose the result with higher confidence
        all_fields = set(list(regex_data.keys()) + list(llm_data.keys()))
        
        for field in all_fields:
            regex_field = regex_data.get(field)
            llm_field = llm_data.get(field)
            
            if not regex_field:
                # Only LLM has it
                merged[field] = llm_field
            elif not llm_field:
                # Only regex has it
                merged[field] = regex_field
            else:
                # Both have it
                regex_conf = regex_field.get('confidence', 0)
                llm_conf = llm_field.get('confidence', 0)
                
                # Prefer LLM for email (better at handling OCR spacing issues)
                if field == 'email_id' and llm_field:
                    merged[field] = llm_field
                # Prefer LLM if prefer_llm flag is set (low confidence cases)
                elif prefer_llm and llm_conf >= regex_conf * 0.9:  # LLM within 10% of regex
                    merged[field] = llm_field
                # Otherwise prefer higher confidence
                elif llm_conf > regex_conf:
                    merged[field] = llm_field
                else:
                    merged[field] = regex_field
        
        # Recalculate overall confidence
        field_confidences = {
            field: data['confidence']
            for field, data in merged.items()
        }
        overall_confidence = self.confidence_calc.calculate_overall_confidence(field_confidences)
        
        detected_fields = self.confidence_calc.get_detected_fields(field_confidences)
        missing_fields = self.confidence_calc.get_missing_fields(field_confidences, self.ALL_FIELDS)
        
        return {
            'extracted_data': merged,
            'overall_confidence': overall_confidence,
            'raw_text': regex_result.get('raw_text', ''),
            'parsing_metadata': {
                'total_lines': regex_result.get('parsing_metadata', {}).get('total_lines', 0),
                'detected_fields': detected_fields,
                'missing_fields': missing_fields,
                'extraction_method': 'hybrid_regex_llm'
            }
        }
    
    def _split_into_lines(self, text: str) -> List[str]:
        """Split text into lines, cleaning whitespace"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return lines
    
    def _extract_email(self, text: str, lines: List[str]) -> Optional[Dict]:
        """Extract email address - general pattern matching, let LLM handle OCR issues"""
        # General email pattern - matches standard email format
        email_pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        
        match = re.search(email_pattern, text)
        if match:
            email = match.group(0)
            confidence = self.confidence_calc.calculate_email_confidence(email)
            return {
                'value': email,
                'confidence': confidence,
                'source': 'regex_match'
            }
        
        return None
    
    def _extract_phones(self, text: str, lines: List[str]) -> Dict[str, Dict]:
        """Extract phone numbers (mobile and landline)"""
        results = {}
        
        # Look for labeled phone numbers first (more reliable)
        # Handle cases where label and number might be on different lines (e.g., "Dir\n: 044-2220")
        mobile_label_pattern = r'(?:mobile|mob|cell|phone|m)[\s:]*\s*(?:[\n\r]+)?\s*([+\d\s\-\(\)]{8,})'
        landline_label_pattern = r'(?:landline|tel|telephone|dir|direct|office|off|t)[\s:]*\s*(?:[\n\r]+)?\s*([+\d\s\-\(\)]{7,})'
        
        # Check for mobile with label (handle multiline)
        mobile_match = re.search(mobile_label_pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if mobile_match:
            mobile = mobile_match.group(1).strip()
            # Clean up - remove newlines, extra spaces, stop at next label
            mobile = re.sub(r'\s+', ' ', mobile)
            mobile = re.split(r'[:\n]', mobile)[0].strip()
            cleaned = re.sub(r'[\s\-\(\)\.]', '', mobile)
            if len(cleaned) >= 10:
                results['mobile_number'] = {
                    'value': mobile,
                    'confidence': self.confidence_calc.calculate_phone_confidence(cleaned, is_mobile=True),
                    'source': 'label_match'
                }
        
        # Check for landline with label (handle multiline)
        landline_match = re.search(landline_label_pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if landline_match:
            landline = landline_match.group(1).strip()
            # Clean up - remove newlines, extra spaces, stop at next label or separator
            landline = re.sub(r'\s+', ' ', landline)
            # Stop at pipe, semicolon, or next label
            landline = re.split(r'[|;:\n]|(?:mobile|mob|email|e-mail|fax)', landline, flags=re.IGNORECASE)[0].strip()
            cleaned = re.sub(r'[\s\-\(\)\.]', '', landline)
            # Landline can have country code, so check length more flexibly
            if len(cleaned) >= 8:
                results['landline_number'] = {
                    'value': landline,
                    'confidence': self.confidence_calc.calculate_phone_confidence(cleaned, is_mobile=False),
                    'source': 'label_match'
                }
        
        # If not found by label, use pattern matching
        if 'mobile_number' not in results or 'landline_number' not in results:
            # Phone patterns
            patterns = [
                r'\+91[\s\-]?[6-9]\d{4}[\s\-]?\d{5}',  # Indian mobile with country code
                r'\+?[1-9]\d{0,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,9}',  # International
                r'[6-9]\d{9}',  # Indian mobile (10 digits)
                r'[2-9]\d{2}[\s\-]?\d{3}[\s\-]?\d{4}',  # US format
                r'0\d{2,4}[\s\-]?\d{6,8}',  # Landline with area code (Indian format)
            ]
            
            phones = []
            for pattern in patterns:
                matches = re.finditer(pattern, text)
                for match in matches:
                    phone = match.group(0)
                    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
                    phones.append({
                        'original': phone,
                        'cleaned': cleaned,
                        'position': match.start()
                    })
            
            # Classify as mobile or landline
            for phone_data in phones:
                cleaned = phone_data['cleaned']
                
                # Check if mobile
                is_mobile = (
                    cleaned.startswith('91') and len(cleaned) == 12 and cleaned[2] in '6789' or  # Indian with country code
                    (len(cleaned) == 10 and cleaned[0] in '6789') or  # Indian mobile
                    (len(cleaned) == 10 and cleaned[0] in '23456789') or  # US mobile
                    (len(cleaned) == 11 and cleaned[0] == '1') or  # US with country code
                    phone_data['original'].startswith('+91')  # Explicit Indian mobile
                )
                
                # Check if landline
                is_landline = (
                    cleaned.startswith('0') and len(cleaned) >= 8 or  # Starts with 0 (area code)
                    (len(cleaned) >= 8 and len(cleaned) <= 12 and not is_mobile)
                )
                
                field_name = None
                if is_mobile and 'mobile_number' not in results:
                    field_name = 'mobile_number'
                elif is_landline and 'landline_number' not in results:
                    field_name = 'landline_number'
                
                if field_name:
                    confidence = self.confidence_calc.calculate_phone_confidence(
                        cleaned, is_mobile=is_mobile
                    )
                    results[field_name] = {
                        'value': phone_data['original'],
                        'confidence': confidence,
                        'source': 'regex_match'
                    }
        
        return results
    
    def _extract_name(self, text: str, lines: List[str]) -> Optional[Dict]:
        """Extract name"""
        # Look for "Name:" label
        name_pattern = r'(?:name|nm)[\s:]+([A-Z][a-zA-Z\s]+)'
        match = re.search(name_pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            return {
                'value': name,
                'confidence': self.confidence_calc.calculate_name_confidence(name, 'label_match'),
                'source': 'label_match'
            }
        
        # Check early lines (usually name appears in first few lines, after company name)
        # Skip lines that look like company names, addresses, designations, or taglines
        for i, line in enumerate(lines[:5]):  # Check first 5 lines
            # Skip if it looks like company name (contains "Bank", "Limited", "Inc", etc.)
            if re.search(r'\b(bank|limited|ltd|inc|corporation|corp|company)\b', line, re.IGNORECASE):
                continue
            
            # Skip if it looks like designation (contains "Manager", "Director", etc.)
            if re.search(r'\b(manager|director|engineer|executive|president|ceo|cfo|cto|officer)\b', line, re.IGNORECASE):
                continue
            
            # Skip if it looks like address (contains numbers, "Street", "Road", etc.)
            if re.search(r'\d+.*(street|road|avenue|lane|salai|nagar|pradesh|state)', line, re.IGNORECASE):
                continue
            
            # Skip common taglines/slogans (these often appear before the actual name)
            # Common patterns: "PASSION AT WORK", "EXCELLENCE IN SERVICE", etc.
            tagline_patterns = [
                r'\b(passion|excellence|quality|innovation|leadership|vision|mission|values|commitment|dedication)\b.*\b(at|in|for|with|through|towards)\b',
                r'\b(at|in|for|with|through|towards)\b.*\b(work|service|quality|excellence|innovation|customer)\b',
                r'^[A-Z\s]{3,}(?:AT|IN|FOR|WITH|THROUGH|TOWARDS)[A-Z\s]{3,}$',  # ALL CAPS taglines
            ]
            # Also check if line is a common tagline phrase (2-4 words, all caps, contains "AT", "IN", etc.)
            if (re.match(r'^[A-Z\s]{5,30}$', line) and 
                re.search(r'\b(AT|IN|FOR|WITH|THROUGH|TOWARDS)\b', line) and
                len(line.split()) <= 4):
                continue
            elif any(re.search(pattern, line, re.IGNORECASE) for pattern in tagline_patterns):
                continue
            
            # Check if it looks like a name (2-6 words, starts with capital, may have initials)
            # Pattern 1: Mixed case - FirstName [Initials] LastName
            name_pattern_mixed = r'^[A-Z][a-z]+(?:\s+[A-Z]{1,3})*(?:\s+[A-Z][a-z]+)*$'
            # Pattern 2: ALL CAPS - FIRSTNAME LASTNAME
            name_pattern_caps = r'^[A-Z]{2,}(?:\s+[A-Z]{2,}){1,4}$'
            
            word_count = len(line.split())
            if 2 <= word_count <= 6:
                if re.match(name_pattern_mixed, line):
                    return {
                        'value': line,
                        'confidence': self.confidence_calc.calculate_name_confidence(line, 'line_1'),
                        'source': f'line_{i+1}'
                    }
                elif re.match(name_pattern_caps, line):
                    # Convert ALL CAPS to Title Case for better readability
                    name_title = ' '.join(word.capitalize() for word in line.split())
                    return {
                        'value': name_title,
                        'confidence': self.confidence_calc.calculate_name_confidence(name_title, 'line_1'),
                        'source': f'line_{i+1}'
                    }
        
        return None
    
    def _extract_organisation(self, text: str, lines: List[str]) -> Optional[Dict]:
        """Extract organisation/company name"""
        # Look for company labels
        org_patterns = [
            r'(?:company|organisation|organization|org|corp|corporation)[\s:]+([A-Z][a-zA-Z0-9\s&.,]+)',
        ]
        
        for pattern in org_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                org = match.group(1).strip()
                # Clean up - remove address parts if present
                org = self._clean_organisation(org)
                return {
                    'value': org,
                    'confidence': self.confidence_calc.calculate_organisation_confidence(org, 'label_match'),
                    'source': 'label_match'
                }
        
        # Look for lines containing company indicators (Bank, Limited, Ltd, Inc, Corp)
        # Priority: lines with "Bank" + "Limited" together are most likely company name
        for i, line in enumerate(lines[:6]):  # Check first 6 lines
            # Check if line contains company indicators
            has_bank = re.search(r'\b(bank)\b', line, re.IGNORECASE)
            has_limited = re.search(r'\b(limited|ltd|inc|incorporated|corporation|corp)\b', line, re.IGNORECASE)
            
            if has_bank or has_limited:
                # Skip if it looks like address (contains numbers, street names)
                if re.search(r'\b(no\.|#|\d+.*street|\d+.*road|\d+.*salai)\b', line, re.IGNORECASE):
                    continue
                
                # Clean up - extract just the company name
                org = self._clean_organisation(line)
                # Prefer lines with both "Bank" and "Limited"
                if has_bank and has_limited and org and len(org.split()) <= 6:
                    return {
                        'value': org,
                        'confidence': self.confidence_calc.calculate_organisation_confidence(org, 'prominent_text'),
                        'source': f'line_{i+1}'
                    }
        
        # Fallback: any line with company indicators
        for i, line in enumerate(lines[:6]):
            if re.search(r'\b(bank|limited|ltd|inc|incorporated|corporation|corp|company)\b', line, re.IGNORECASE):
                if not re.search(r'\b(no\.|#|\d+.*street|\d+.*road)\b', line, re.IGNORECASE):
                    org = self._clean_organisation(line)
                    if org and len(org.split()) <= 6:
                        return {
                            'value': org,
                            'confidence': self.confidence_calc.calculate_organisation_confidence(org, 'prominent_text'),
                            'source': f'line_{i+1}'
                        }
        
        # Additional fallback: Single-word or short all-caps lines (could be company name)
        # Check early lines that are prominent (usually line 1-3)
        for i, line in enumerate(lines[:4]):
            # Skip if already identified as name or designation
            if re.search(r'\b(manager|director|engineer|executive|president|ceo|cfo|cto|officer)\b', line, re.IGNORECASE):
                continue
            # Skip if looks like name (has lowercase or initials pattern)
            if re.match(r'^[A-Z][a-z]+', line) or re.match(r'^[A-Z]{2,}\s+[A-Z]{2,}$', line):
                continue
            # Skip if address
            if re.search(r'\b(no\.|#|\d+|street|road|salai|nagar|pradesh|state|city)\b', line, re.IGNORECASE):
                continue
            
            # Check if it's a short, prominent line (could be company)
            if len(line.split()) <= 3 and len(line) >= 3 and len(line) <= 30:
                # All caps or title case
                if line.isupper() or (line[0].isupper() and not any(c.islower() for c in line[1:])):
                    return {
                        'value': line,
                        'confidence': self.confidence_calc.calculate_organisation_confidence(line, 'prominent_text') * 0.9,  # Slightly lower confidence
                        'source': f'line_{i+1}_fallback'
                    }
        
        return None
    
    def _clean_organisation(self, text: str) -> str:
        """Clean organisation name - remove address parts"""
        # If text is a single line, clean it
        if '\n' not in text:
            # Remove trailing address parts (after comma, or starting with "No.")
            # Extract up to company indicator
            match = re.search(r'^([^,]+?(?:bank|limited|ltd|inc|incorporated|corporation|corp)[^,]*?)(?:,|$)', text, re.IGNORECASE)
            if match:
                result = match.group(1).strip()
                # Remove any trailing "No" or numbers
                result = re.sub(r'\s+No\.?\s*$', '', result, flags=re.IGNORECASE)
                return result
            return text.strip()
        
        # If multiple lines, process each
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            # Skip address lines
            if re.match(r'^(No\.|#|\d+).*', line, re.IGNORECASE):  # Starts with "No.", "#", or number
                continue
            if re.search(r'\b(street|road|avenue|lane|salai|nagar|pradesh|state|city|pin|pincode|zip)\b', line, re.IGNORECASE):
                continue
            if re.match(r'^[A-Z][a-z]+,\s*$', line):  # City name with comma only
                continue
            if re.match(r'^\d{5,6}[\s\-]?\d*\.?$', line):  # PIN code
                continue
            cleaned_lines.append(line)
        
        # Join and return first meaningful line (usually company name)
        result = ' '.join(cleaned_lines).strip()
        # Extract up to company indicator, stop at comma or address
        match = re.search(r'^([^,]+?(?:bank|limited|ltd|inc|incorporated|corporation|corp)[^,]*?)(?:,|$)', result, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
            # Remove trailing "No" or standalone words that are addresses
            result = re.sub(r'\s+No\.?\s*$', '', result, flags=re.IGNORECASE)
            return result
        
        return result
    
    def _extract_designation(self, text: str, lines: List[str]) -> Optional[Dict]:
        """Extract designation/title"""
        # Skip label-based matching - it's too greedy and picks up wrong text
        # Rely on line-based detection which is more accurate
        
        # Look for designation in lines (usually appears after name, before company)
        # Common pattern: Name -> Designation -> Company
        for i, line in enumerate(lines[:6]):  # Check first 6 lines
            # Check if line contains designation keywords
            if re.search(r'\b(manager|director|engineer|executive|president|ceo|cfo|cto|officer|head|lead|senior|junior|principal|chief|vice|associate|general)\b', line, re.IGNORECASE):
                # Check if it's not a company name (doesn't contain "Bank", "Limited", etc.)
                if not re.search(r'\b(bank|limited|ltd|inc|corporation|corp|company)\b', line, re.IGNORECASE):
                    # May span multiple lines - check next line if current is short or looks incomplete
                    designation = line
                    # Check if current line looks incomplete (short, or ends with common designation words that suggest continuation)
                    is_incomplete = (len(line.split()) <= 3 or 
                                   re.search(r'\b(manager|director|head|chief|general|senior|executive)\s*$', line, re.IGNORECASE))
                    
                    if i + 1 < len(lines) and is_incomplete:
                        next_line = lines[i + 1].strip()
                        # Skip if next line is company name (check for company indicators OR short all-caps that's likely company)
                        is_company_name = (
                            re.search(r'\b(bank|limited|ltd|inc|incorporated|corporation|corp|company)\b', next_line, re.IGNORECASE) or
                            # Short all-caps line (1-3 words, 2-15 chars) that doesn't look like designation continuation
                            (re.match(r'^[A-Z]{2,15}(?:\s+[A-Z]{2,15}){0,2}$', next_line) and 
                             len(next_line.split()) <= 3 and
                             not re.search(r'\b(head|treasury|finance|corporate|group|department|division|unit|team|section|operations|sales|marketing)\b', next_line, re.IGNORECASE))
                        )
                        
                        if is_company_name:
                            pass  # Don't combine - next line is company name
                        # If next line looks like designation continuation (contains department/function words, or is all caps short phrase)
                        elif (re.search(r'\b(head|treasury|finance|corporate|group|department|division|unit|team|section|operations|sales|marketing)\b', next_line, re.IGNORECASE) or
                              (re.match(r'^[A-Z\s\-]{2,20}$', next_line) and len(next_line.split()) <= 3)):
                            designation = f"{line} {next_line}"
                            # Stop here - don't continue to next lines
                            return {
                                'value': designation.strip(),
                                'confidence': self.confidence_calc.calculate_designation_confidence(designation, 'inferred'),
                                'source': f'line_{i+1}_{i+2}'
                            }
                    
                    # Single line designation - clean up and return
                    # Remove any trailing "No" or address parts
                    designation = re.sub(r'\s+No\.?\s*$', '', designation, flags=re.IGNORECASE)
                    # Stop at company name if present in the same line (split by common separators)
                    # Check if designation contains company name - if so, extract only the designation part
                    parts = re.split(r'[|,;]', designation)
                    if len(parts) > 1:
                        # Take the first part that looks like designation (contains designation keywords)
                        for part in parts:
                            if re.search(r'\b(manager|director|engineer|executive|president|ceo|cfo|cto|officer|head|lead|senior|junior|principal|chief|vice|associate|general)\b', part, re.IGNORECASE):
                                designation = part.strip()
                                break
                    # Also check if next line is company name and we accidentally included it
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # If next line is likely company name (short, all caps, or contains company indicators)
                        if (len(next_line.split()) <= 3 and 
                            (re.match(r'^[A-Z\s]{2,30}$', next_line) or 
                             re.search(r'\b(bank|limited|ltd|inc|corporation|corp|company)\b', next_line, re.IGNORECASE))):
                            # Make sure designation doesn't end with this company name
                            if designation.upper().endswith(next_line.upper()):
                                designation = designation[:len(designation) - len(next_line)].strip()
                                # Remove trailing dash or hyphen
                                designation = re.sub(r'[\s\-]+$', '', designation)
                    
                    return {
                        'value': designation.strip(),
                        'confidence': self.confidence_calc.calculate_designation_confidence(designation, 'inferred'),
                        'source': f'line_{i+1}'
                    }
        
        # Look for common designations as fallback
        common_designations = [
            r'\b(?:Senior|Junior|Lead|Principal|Chief|Head|Vice|Associate|General)\s+[A-Z][a-zA-Z]+\b',
            r'\b(?:Manager|Director|Engineer|Executive|President|CEO|CFO|CTO)\b',
        ]
        
        for pattern in common_designations:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                designation = match.group(0)
                return {
                    'value': designation,
                    'confidence': self.confidence_calc.calculate_designation_confidence(designation, 'inferred'),
                    'source': 'inferred'
                }
        
        return None
    
    def _empty_result(self) -> Dict:
        """Return empty result structure"""
        return {
            'extracted_data': {},
            'overall_confidence': 0.0,
            'raw_text': '',
            'parsing_metadata': {
                'total_lines': 0,
                'detected_fields': [],
                'missing_fields': self.ALL_FIELDS,
                'extraction_method': 'rule_based'
            }
        }

