"""Industry-standard label normalization for duplicate detection."""

import unicodedata
import re


class LabelNormalizer:
    """
    Normalizes labels using industry-standard techniques.
    
    Normalization steps (as per knowledge graph quality standards):
    1. Unicode normalization (NFKD - compatibility decomposition)
    2. Diacritic removal (combining characters)
    3. Case folding (more aggressive than lowercase)
    4. Punctuation removal (keep alphanumeric and spaces)
    5. Whitespace normalization (collapse multiple spaces, strip)
    
    References:
        - Unicode Standard Annex #15: Unicode Normalization Forms
        - Knowledge Graph Quality: Zaveri et al. (2016)
    """
    
    @staticmethod
    def normalize(label: str) -> str:
        """
        Normalize label string.
        
        Args:
            label: Raw label string
            
        Returns:
            Normalized label string
            
        Examples:
            >>> LabelNormalizer.normalize("World War II")
            'world war ii'
            >>> LabelNormalizer.normalize("Café")
            'cafe'
            >>> LabelNormalizer.normalize("D-Day!!!")
            'd day'
        """
        if not label:
            return ""
        
        # Unicode normalization (NFKD = compatibility decomposition)
        label = unicodedata.normalize('NFKD', label)
        
        # Remove diacritics (combining characters)
        label = ''.join(c for c in label if not unicodedata.combining(c))
        
        # Case folding (more aggressive than lowercase)
        label = label.casefold()
        
        # Remove punctuation (keep alphanumeric and spaces)
        label = re.sub(r'[^\w\s]', '', label)
        
        # Normalize whitespace (collapse multiple spaces, strip)
        label = re.sub(r'\s+', ' ', label).strip()
        
        return label
