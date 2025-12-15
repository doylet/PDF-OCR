"""
Region analyzer that detects region type and routes to appropriate extractor.
"""
import logging
import re
from typing import List, Dict, Optional, Tuple
from app.models.api import Region

logger = logging.getLogger(__name__)


class RegionType:
    """Region type classifications"""
    TABLE = "table"
    KEY_VALUE = "key_value"
    LIST = "list"
    TOTALS = "totals"
    UNKNOWN = "unknown"


class RegionAnalyzer:
    """Analyze OCR text to determine region type and optimal extraction strategy"""
    
    @staticmethod
    def analyze_region(text: str) -> Tuple[str, Dict]:
        """
        Analyze OCR text to determine region type and extraction hints.
        
        Returns:
            (region_type, hints) where hints contains extraction parameters
        """
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if len(lines) < 3:
            return RegionType.UNKNOWN, {}
        
        # Calculate various features
        features = RegionAnalyzer._extract_features(lines)
        
        # Score each region type
        scores = {
            RegionType.TABLE: RegionAnalyzer._score_table(features, lines),
            RegionType.KEY_VALUE: RegionAnalyzer._score_key_value(features, lines),
            RegionType.LIST: RegionAnalyzer._score_list(features, lines),
            RegionType.TOTALS: RegionAnalyzer._score_totals(features, lines),
        }
        
        # Choose highest scoring type
        region_type = max(scores.items(), key=lambda x: x[1])[0]
        confidence = scores[region_type]
        
        if confidence < 0.3:
            region_type = RegionType.UNKNOWN
        
        # Extract hints for the detected type
        hints = RegionAnalyzer._extract_hints(region_type, features, lines)
        
        logger.info(f"Region analysis: type={region_type}, confidence={confidence:.2f}, hints={hints}")
        return region_type, hints
    
    @staticmethod
    def _extract_features(lines: List[str]) -> Dict:
        """Extract statistical features from text lines"""
        features = {
            'num_lines': len(lines),
            'num_dates': 0,
            'num_volumes': 0,
            'num_currency': 0,
            'num_percentages': 0,
            'num_colons': 0,
            'has_table_headers': False,
            'repeated_words': {},
            'has_totals_footer': False,
        }
        
        # Pattern detection
        date_pattern = re.compile(r'\d{1,2}\s+[A-Z][a-z]{2}|\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}')
        volume_pattern = re.compile(r'\d+(\.\d+)?(MB|GB|KB|TB)', re.IGNORECASE)
        currency_pattern = re.compile(r'\$\d+(\.\d{2})?|USD|AUD|EUR')
        percentage_pattern = re.compile(r'\d+(\.\d+)?%')
        
        # Common table headers
        table_headers = ['date', 'description', 'volume', 'amount', 'qty', 'quantity', 
                        'price', 'total', 'time', 'duration', 'type', 'status']
        
        word_counts = {}
        
        for line in lines:
            lower_line = line.lower()
            
            # Count patterns
            features['num_dates'] += len(date_pattern.findall(line))
            features['num_volumes'] += len(volume_pattern.findall(line))
            features['num_currency'] += len(currency_pattern.findall(line))
            features['num_percentages'] += len(percentage_pattern.findall(line))
            features['num_colons'] += line.count(':')
            
            # Check for table headers
            if any(header in lower_line for header in table_headers):
                features['has_table_headers'] = True
            
            # Count word repetitions
            words = lower_line.split()
            for word in words:
                if len(word) > 3:  # Ignore short words
                    word_counts[word] = word_counts.get(word, 0) + 1
            
            # Check for totals footer
            if 'total' in lower_line and ('volume' in lower_line or 'amount' in lower_line or 'due' in lower_line):
                features['has_totals_footer'] = True
        
        # Find most repeated words (indicates structured data)
        features['repeated_words'] = {k: v for k, v in word_counts.items() if v >= 3}
        
        return features
    
    @staticmethod
    def _score_table(features: Dict, lines: List[str]) -> float:
        """Score likelihood that region contains a table"""
        score = 0.0
        
        # Strong table indicators
        if features['has_table_headers']:
            score += 0.4
        
        if features['num_dates'] >= 3:
            score += 0.3
        
        if len(features['repeated_words']) >= 1:
            score += 0.2
        
        if features['num_lines'] >= 5:
            score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def _score_key_value(features: Dict, lines: List[str]) -> float:
        """Score likelihood that region contains key-value pairs"""
        score = 0.0
        
        # Key-value indicators
        colon_ratio = features['num_colons'] / max(features['num_lines'], 1)
        if colon_ratio > 0.3:
            score += 0.5
        
        if features['num_lines'] < 10:  # Key-value regions tend to be compact
            score += 0.2
        
        if not features['has_table_headers']:  # Less likely to have headers
            score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def _score_list(features: Dict, lines: List[str]) -> float:
        """Score likelihood that region contains a list"""
        score = 0.0
        
        # List indicators
        if len(features['repeated_words']) >= 1:
            score += 0.3
        
        if features['num_lines'] >= 3:
            score += 0.2
        
        return min(score, 1.0)
    
    @staticmethod
    def _score_totals(features: Dict, lines: List[str]) -> float:
        """Score likelihood that region contains totals/summary"""
        score = 0.0
        
        if features['has_totals_footer']:
            score += 0.6
        
        if features['num_currency'] >= 1 or features['num_volumes'] >= 1:
            score += 0.3
        
        if features['num_lines'] < 5:  # Totals are typically compact
            score += 0.1
        
        return min(score, 1.0)
    
    @staticmethod
    def _extract_hints(region_type: str, features: Dict, lines: List[str]) -> Dict:
        """Extract extraction hints based on region type"""
        hints = {}
        
        if region_type == RegionType.TABLE:
            # Detect schema hints
            if features['num_dates'] >= 3 and features['num_volumes'] >= 3:
                hints['schema'] = 'usage_by_day'
                hints['columns'] = ['date', 'description', 'volume']
            elif features['num_dates'] >= 3 and features['num_currency'] >= 3:
                hints['schema'] = 'transactions'
                hints['columns'] = ['date', 'description', 'amount']
            
        elif region_type == RegionType.KEY_VALUE:
            hints['extraction_method'] = 'colon_split'
        
        return hints
