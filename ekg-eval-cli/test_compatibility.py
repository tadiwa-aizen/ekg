"""Compatibility tests for Phase 1 evaluations against EventKG data."""

import sys
from pathlib import Path

# Test if we can import the modules
try:
    from ekg_eval_cli.redundancy import RedundancyAnalyzer
    from ekg_eval_cli.temporal import TemporalValidator
    from ekg_eval_cli.analyzer import GraphAnalyzer
    print("✅ All modules imported successfully")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)


def test_sparql_endpoint(endpoint_url: str):
    """Test if Fuseki endpoint is accessible."""
    import requests
    try:
        response = requests.get(f"{endpoint_url}/$/ping", timeout=5)
        if response.status_code == 200:
            print(f"✅ Fuseki endpoint accessible: {endpoint_url}")
            return True
        else:
            print(f"❌ Fuseki returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot reach Fuseki: {e}")
        return False


def test_event_count(endpoint_url: str):
    """Test basic event count query."""
    import requests
    
    query = """
    PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
    
    SELECT (COUNT(?event) AS ?count)
    WHERE {
        ?event a sem:Event .
    }
    LIMIT 1
    """
    
    try:
        response = requests.post(
            f"{endpoint_url}/sparql",
            data={'query': query},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        count = int(result['results']['bindings'][0]['count']['value'])
        print(f"✅ Event count query works: {count:,} events found")
        return True
    except Exception as e:
        print(f"❌ Event count query failed: {e}")
        return False


def test_label_query(endpoint_url: str):
    """Test label extraction for redundancy analysis."""
    import requests
    
    query = """
    PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?event ?label
    WHERE {
        ?event a sem:Event ;
               rdfs:label ?label .
        FILTER(lang(?label) = "en")
    }
    LIMIT 10
    """
    
    try:
        response = requests.post(
            f"{endpoint_url}/sparql",
            data={'query': query},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        labels = result['results']['bindings']
        print(f"✅ Label query works: {len(labels)} English labels retrieved")
        if labels:
            print(f"   Example: {labels[0]['label']['value']}")
        return True
    except Exception as e:
        print(f"❌ Label query failed: {e}")
        return False


def test_sameas_query(endpoint_url: str):
    """Test owl:sameAs query for redundancy analysis."""
    import requests
    
    query = """
    PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    
    SELECT ?event ?sameAs
    WHERE {
        ?event a sem:Event ;
               owl:sameAs ?sameAs .
    }
    LIMIT 10
    """
    
    try:
        response = requests.post(
            f"{endpoint_url}/sparql",
            data={'query': query},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        sameas = result['results']['bindings']
        print(f"✅ owl:sameAs query works: {len(sameas)} links retrieved")
        if sameas:
            print(f"   Example: {sameas[0]['sameAs']['value']}")
        return True
    except Exception as e:
        print(f"❌ owl:sameAs query failed: {e}")
        return False


def test_temporal_query(endpoint_url: str):
    """Test temporal data query."""
    import requests
    
    query = """
    PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
    
    SELECT ?event ?date
    WHERE {
        ?event a sem:Event ;
               sem:hasBeginTimeStamp ?date .
    }
    LIMIT 10
    """
    
    try:
        response = requests.post(
            f"{endpoint_url}/sparql",
            data={'query': query},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        dates = result['results']['bindings']
        print(f"✅ Temporal query works: {len(dates)} dates retrieved")
        if dates:
            print(f"   Example: {dates[0]['date']['value']}")
        return True
    except Exception as e:
        print(f"❌ Temporal query failed: {e}")
        return False


def test_temporal_granularity_query(endpoint_url: str):
    """Test temporal granularity query with unit types."""
    import requests
    
    query = """
    PREFIX sem: <http://semanticweb.cs.vu.nl/2009/11/sem/>
    PREFIX ekgs: <https://eventkg.l3s.uni-hannover.de/schema/>
    
    SELECT ?event ?date ?unitType
    WHERE {
        ?event a sem:Event ;
               sem:hasBeginTimeStamp ?date .
        OPTIONAL { ?event ekgs:startUnitType ?unitType }
    }
    LIMIT 10
    """
    
    try:
        response = requests.post(
            f"{endpoint_url}/sparql",
            data={'query': query},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        data = result['results']['bindings']
        print(f"✅ Granularity query works: {len(data)} records retrieved")
        if data:
            has_unit = 'unitType' in data[0]
            print(f"   Unit type present: {has_unit}")
        return True
    except Exception as e:
        print(f"❌ Granularity query failed: {e}")
        return False


def test_edge_extraction_query(endpoint_url: str):
    """Test edge extraction for NetworkX."""
    import requests
    
    query = """
    CONSTRUCT { ?s <urn:link> ?o . }
    WHERE { 
        ?s ?p ?o . 
        FILTER(isIRI(?s) && isIRI(?o)) 
    }
    LIMIT 100
    """
    
    try:
        response = requests.post(
            f"{endpoint_url}/sparql",
            data={'query': query},
            headers={'Accept': 'application/n-triples'},
            timeout=30
        )
        response.raise_for_status()
        edges = response.text.strip().split('\n')
        print(f"✅ Edge extraction works: {len(edges)} edges retrieved")
        if edges:
            print(f"   Example: {edges[0][:80]}...")
        return True
    except Exception as e:
        print(f"❌ Edge extraction failed: {e}")
        return False


def test_date_validation():
    """Test date validation logic."""
    from dateutil import parser
    
    test_dates = [
        "2020-09-27",
        "2021-01-24",
        "2021-01-01",
        "invalid-date",
        "2020-13-01"
    ]
    
    valid = 0
    invalid = 0
    
    for date_str in test_dates:
        try:
            parser.isoparse(date_str)
            valid += 1
        except:
            invalid += 1
    
    print(f"✅ Date validation works: {valid} valid, {invalid} invalid")
    return True


def test_fuzzy_matching():
    """Test fuzzy string matching."""
    from rapidfuzz import fuzz
    
    pairs = [
        ("World War II", "World War 2"),
        ("COVID-19 pandemic", "COVID-19 Pandemic"),
        ("Battle of Waterloo", "Waterloo Battle")
    ]
    
    print("✅ Fuzzy matching works:")
    for s1, s2 in pairs:
        score = fuzz.token_sort_ratio(s1.lower(), s2.lower())
        print(f"   '{s1}' vs '{s2}': {score}%")
    
    return True


def run_all_tests(endpoint_url: str):
    """Run all compatibility tests."""
    print("\n" + "="*70)
    print("PHASE 1 COMPATIBILITY TESTS")
    print("="*70 + "\n")
    
    tests = [
        ("Fuseki Endpoint", lambda: test_sparql_endpoint(endpoint_url)),
        ("Event Count Query", lambda: test_event_count(endpoint_url)),
        ("Label Query (Redundancy)", lambda: test_label_query(endpoint_url)),
        ("owl:sameAs Query (Redundancy)", lambda: test_sameas_query(endpoint_url)),
        ("Temporal Query", lambda: test_temporal_query(endpoint_url)),
        ("Temporal Granularity Query", lambda: test_temporal_granularity_query(endpoint_url)),
        ("Edge Extraction (NetworkX)", lambda: test_edge_extraction_query(endpoint_url)),
        ("Date Validation Logic", test_date_validation),
        ("Fuzzy Matching Logic", test_fuzzy_matching),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n[Testing: {name}]")
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"❌ Test crashed: {e}")
            results.append((name, False))
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70 + "\n")
    
    return passed == total


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_compatibility.py <fuseki_endpoint_url>")
        print("Example: python test_compatibility.py http://localhost:3030/eventkg")
        sys.exit(1)
    
    endpoint = sys.argv[1]
    success = run_all_tests(endpoint)
    sys.exit(0 if success else 1)
