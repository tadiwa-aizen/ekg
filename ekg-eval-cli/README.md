# EKG Evaluation CLI

A command-line tool for evaluating Event-Centric Knowledge Graphs using Apache Jena, Fuseki, and NetworkX.

## Overview

The EKG Evaluation CLI automates the workflow of loading RDF data into a TDB2 database, starting a Fuseki SPARQL server, and calculating graph structural metrics. It provides researchers with a simple, single-command interface to evaluate the connectivity and cohesion of their Event-Centric Knowledge Graphs.

## Features

- **Automated Workflow**: Single command execution handles database loading, server startup, and analysis
- **Smart Detection**: Automatically finds Jena and Fuseki installations in the current directory
- **Database Reuse**: Skips loading if database already exists for faster subsequent runs
- **Server Management**: Detects and reuses running Fuseki instances
- **Comprehensive Metrics**: Calculates connectivity and cohesion metrics using NetworkX
- **Multiple Output Formats**: Results saved to console, JSON, and CSV files
- **Verbose Mode**: Detailed progress information for debugging and monitoring

## Requirements

### External Dependencies

Before using this tool, you must have the following installed:

1. **Apache Jena** (version 5.6.0 or higher)
   - Download from: https://jena.apache.org/download/
   - Extract to a directory (e.g., `apache-jena-5.6.0/`)
   - The tool will automatically find it if placed in the current directory

2. **Apache Jena Fuseki** (version 5.6.0 or higher)
   - Download from: https://jena.apache.org/download/
   - Extract to a directory (e.g., `apache-jena-fuseki-5.6.0/`)
   - The tool will automatically find it if placed in the current directory

3. **Python** (version 3.8 or higher)

### Python Dependencies

The following Python packages are required (automatically installed with pip):

- `click>=8.0` - CLI framework
- `networkx>=3.0` - Graph analysis
- `requests>=2.28` - HTTP client for SPARQL queries
- `rdflib>=6.0` - RDF parsing utilities

## Installation

### Option 1: Install from Source (Development)

```bash
# Clone or navigate to the project directory
cd /path/to/ekg-eval-cli

# Install in editable mode
pip install -e .
```

### Option 2: Install Dependencies Only

```bash
# Install required Python packages
pip install -r requirements.txt

# Run directly with Python
python -m ekg_eval_cli.cli /path/to/ekg/folder
```

### Verify Installation

```bash
# Check version
ekg-eval-cli --version

# Display help
ekg-eval-cli --help
```

## Usage

### Basic Usage

```bash
ekg-eval-cli /path/to/ekg/folder
```

This command will:
1. Validate that the folder contains `.nt` (N-Triples) files
2. Load the data into a TDB2 database (if not already loaded)
3. Start the Fuseki SPARQL server (if not already running)
4. Extract graph edges using SPARQL queries
5. Calculate connectivity and cohesion metrics
6. Display results and save to JSON and CSV files

### Usage Examples

#### With Verbose Output

```bash
ekg-eval-cli /path/to/ekg/folder --verbose
```

Displays detailed progress information including:
- Path resolution
- Database loading progress
- Server startup status
- Query execution details
- Metric calculations

#### With Custom Output Directory

```bash
ekg-eval-cli /path/to/ekg/folder --output-dir ./my_results
```

Saves JSON and CSV output files to the specified directory instead of the default `./ekg_results`.

#### With Custom Jena and Fuseki Paths

```bash
ekg-eval-cli /path/to/ekg/folder \
  --jena-home /opt/apache-jena-5.6.0 \
  --fuseki-home /opt/apache-jena-fuseki-5.6.0
```

Use this when Jena and Fuseki are installed in non-standard locations.

#### With Custom Evaluation Parameters

```bash
ekg-eval-cli /path/to/ekg/folder \
  --fuzzy-threshold 0.90 \
  --fuzzy-sample-size 2000 \
  --temporal-sample-size 1500 \
  --max-properties 100
```

Customize evaluation parameters:
- `--fuzzy-threshold`: Similarity threshold for fuzzy duplicate detection (0.0-1.0, default: 0.85)
- `--fuzzy-sample-size`: Number of events to sample for fuzzy matching (default: 1000)
- `--temporal-sample-size`: Number of temporal relations to sample (default: 1000)
- `--max-properties`: Maximum properties to analyze for type consistency (default: 50)

#### Complete Example

```bash
ekg-eval-cli ./event-kg \
  --verbose \
  --output-dir ./results \
  --jena-home /opt/jena \
  --fuseki-home /opt/fuseki \
  --fuzzy-threshold 0.90 \
  --max-properties 100
```

## Command-Line Options

### Arguments

- `EKG_FOLDER` (required): Path to directory containing N-Triples (`.nt`) files

### Options

**General:**
- `--verbose`: Enable verbose output with detailed progress information
- `--output-dir PATH`: Custom output directory for results (default: `./ekg_results`)
- `--jena-home PATH`: Path to Apache Jena installation directory
- `--fuseki-home PATH`: Path to Apache Jena Fuseki installation directory
- `--version`: Display version information
- `--help`: Display help message with usage information

**Evaluation Parameters:**
- `--fuzzy-threshold FLOAT`: Fuzzy matching similarity threshold (0.0-1.0, default: 0.85)
- `--fuzzy-sample-size INT`: Events to sample for fuzzy matching (default: 1000)
- `--temporal-sample-size INT`: Temporal relations to sample (default: 1000)
- `--max-properties INT`: Max properties for type consistency analysis (default: 50)

## Output

### Console Output

The tool displays a summary of calculated metrics:

```
Graph Connectivity Metrics
==================================================
Total Nodes:              12,345
Total Edges:              45,678
Connected Components:     5
Giant Component Size:     12,000
Giant Component Ratio:    0.972
Average Clustering:       0.456
Edge Connectivity:        3
==================================================
```

### JSON Output

Results are saved to `ekg_results/metrics_YYYYMMDD_HHMMSS.json`:

```json
{
  "num_components": 5,
  "giant_component_size": 12000,
  "total_nodes": 12345,
  "giant_component_ratio": 0.972,
  "total_edges": 45678,
  "avg_clustering": 0.456,
  "edge_connectivity": 3,
  "timestamp": "2025-01-15T10:30:45",
  "ekg_folder": "/path/to/ekg/folder"
}
```

### CSV Output

Results are saved to `ekg_results/metrics_YYYYMMDD_HHMMSS.csv`:

```csv
metric,value
num_components,5
giant_component_size,12000
total_nodes,12345
giant_component_ratio,0.972
total_edges,45678
avg_clustering,0.456
edge_connectivity,3
timestamp,2025-01-15T10:30:45
ekg_folder,/path/to/ekg/folder
```

## Evaluation Framework

This tool implements a comprehensive evaluation framework for Event-Centric Knowledge Graphs across five major dimensions:

### 1. Structural Metrics (Phase 1 - IMPLEMENTED ✅)

**Graph Connectivity and Cohesion:**
- **Total Nodes**: Number of unique nodes (IRIs) in the graph
- **Total Edges**: Number of unique edges (IRI-to-IRI relationships)
- **Connected Components**: Number of disconnected subgraphs
- **Giant Component Size**: Number of nodes in the largest connected component
- **Giant Component Ratio**: Proportion of nodes in the giant component (size/total)
- **Average Clustering**: Mean clustering coefficient across all nodes
- **Edge Connectivity**: Minimum number of edges that must be removed to disconnect the graph

**Graph Size and Density:**
- **Average Degree**: Mean number of connections per node
- **Graph Density**: Ratio of actual edges to possible edges

**Redundancy (Duplication Rate):**
- **Exact Label Duplicates**: Events with identical English labels
- **owl:sameAs Overlaps**: Events sharing external entity links
- **Fuzzy Duplicates**: Near-duplicate detection using ≥85% similarity matching
- **Duplication Rate**: Percentage of duplicate events in the graph

**Temporal Consistency:**
- **Date Format Validation**: ISO 8601 compliance checking
- **Temporal Granularity**: Distribution of year/month/day/timestamp precision
- **Temporal Coverage**: Percentage of events with temporal information

### 2. Semantic Consistency and Correctness (Phase 2 - IMPLEMENTED ✅)

**Schema Alignment and Ontology Conformance:**
- **Label Coverage**: Percentage of events with rdfs:label
- **Date Coverage**: Percentage of events with temporal data
- **Schema Conformance Rate**: Events with complete required properties
- **Non-standard Properties**: Detection of custom/non-standard predicates
- **External Vocabulary Usage**: Usage of schema.org, DBpedia, Wikidata

**Type & Role Consistency:**
- **Domain Conformity**: Subjects match expected classes for properties
- **Range Conformity**: Objects match expected classes/datatypes
- **Overall Type Consistency**: Combined domain and range conformance

### 3. Completeness & Coverage (Phase 2 - IMPLEMENTED ✅)

**Population Completeness:**
- **Total Event Instances**: Count of all event instances
- **Used vs Declared Classes**: Active classes vs schema-defined classes
- **Schema Coverage**: Percentage of schema classes actually used
- **Population Completeness**: Events with complete minimal data
- **Class Usage Efficiency**: Distribution of events across classes
- **Property Usage Statistics**: Most frequently used properties

### 4. Temporal and Causal Coherence (Phase 1 Partial - Temporal ✅, Causal 🚧)

**Schema Alignment and Ontology Conformance:**
- Schema conformance rate
- External vocabulary alignment (schema.org, DBpedia, Wikidata)
- Type alignment and conflict detection
- Domain and range correctness validation

**Factual Accuracy:**
- Cross-validation against Wikidata and DBpedia
- Temporal consistency checks (ISO 8601 validation)
- Geographic verification via GeoNames API
- Precision, Recall, and F1 scores against gold standards

**Type & Role Consistency:**
- Property domain/range validation
- Type consistency checking across the ontology

### 3. Completeness (Planned)

**Coverage (Population Completeness):**
- Total event instances vs. declared schema classes
- Schema coverage percentage
- Population completeness percentage
- Class usage efficiency

**Schema Completeness:**
- Class breadth and property breadth analysis
- Identification of undefined schema parts
- Class and property usage validation
- Expressiveness gap scoring

**Property Completeness:**
- Coverage of required properties per event
- Property usage patterns

### 4. Temporal and Causal Coherence (Planned)

**Temporal Consistency:**
- Date format validation
- Temporal ordering verification
- Granularity consistency analysis

**Causal Coherence:**
- Cycle detection in causal graphs
- Temporal validation of cause-effect relationships
- Causality correctness assessment

**Narrative Coherence:**
- Event sequence validation
- Multi-step event ordering
- Logical coherence checking

### 5. Downstream Performance (Planned)

**Precision and Recall:**
- Triple-level comparison against gold standards
- Per-predicate metrics (event type, date, location, participants)
- Overall F1 scores

### Scoring Framework

The complete evaluation framework provides a machine-gradable score out of 100 points:
- Structural Integrity: 20 points
- Semantic Alignment & Schema Quality: 20 points
- Completeness & Coverage: 20 points
- Temporal & Causal Coherence: 20 points
- Downstream Performance: 20 points

### Current Implementation Status:**
- ✅ **Phase 1 Complete**: Graph Connectivity, Density, Redundancy, Temporal Consistency
- ✅ **Phase 2 Complete**: Schema Alignment, Coverage & Completeness, Type Consistency
- ❌ **Phase 3 Not Applicable**: EventKG lacks native causal data (see PHASE3_NOT_APPLICABLE.md)
- 🚧 **Phase 4 Planned**: Requires gold standard dataset and external API access

**Implementation: 7/11 components (64%)** - Phases 1 & 2 provide comprehensive structural, temporal, and schema-based evaluation.

## Project Structure

```
ekg-eval-cli/
├── ekg_eval_cli/
│   ├── __init__.py           # Package initialization
│   ├── cli.py                # CLI entry point
│   ├── orchestrator.py       # Workflow orchestration
│   ├── path_resolver.py      # Jena/Fuseki path resolution
│   ├── database.py           # TDB2 database management
│   ├── fuseki.py             # Fuseki server management
│   ├── sparql.py             # SPARQL query execution
│   ├── analyzer.py           # NetworkX graph analysis
│   └── output.py             # Result output handling
├── tests/                    # Test suite
├── setup.py                  # Package configuration
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Troubleshooting

### Error: "Jena installation not found"

**Solution**: Ensure Apache Jena is installed and either:
- Place the `apache-jena-*` folder in the current directory, or
- Use the `--jena-home` option to specify the installation path

### Error: "Fuseki installation not found"

**Solution**: Ensure Apache Jena Fuseki is installed and either:
- Place the `apache-jena-fuseki-*` folder in the current directory, or
- Use the `--fuseki-home` option to specify the installation path

### Error: "EKG folder contains no .nt files"

**Solution**: Verify that your EKG folder contains N-Triples files with the `.nt` extension.

### Error: "Port 3030 already in use"

**Solution**: The tool will detect if Fuseki is already running on port 3030 and reuse it. If another application is using the port, stop it first.

### Database Loading is Slow

**Solution**: Database loading time depends on the size of your `.nt` files. Use `--verbose` to monitor progress. The database is only loaded once; subsequent runs will reuse the existing database.

### Out of Memory Errors

**Solution**: For very large graphs, you may need to increase Python's memory limit or use a machine with more RAM. NetworkX loads the entire graph into memory for analysis.

## Development

### Running Tests

```bash
# Install development dependencies
pip install pytest hypothesis

# Run all tests
pytest tests/

# Run with coverage
pytest --cov=ekg_eval_cli tests/
```

### Code Formatting

```bash
# Install black
pip install black

# Format code
black ekg_eval_cli/
```

## License

MIT License

## Contributing

Contributions are welcome! Please submit issues and pull requests on the project repository.

## Citation

If you use this tool in your research, please cite:

```bibtex
@software{ekg_eval_cli,
  title = {EKG Evaluation CLI: A Tool for Event-Centric Knowledge Graph Evaluation},
  author = {EKG Research Team},
  year = {2025},
  version = {0.1.0}
}
```

## Support

For questions, issues, or feature requests, please open an issue on the project repository.
