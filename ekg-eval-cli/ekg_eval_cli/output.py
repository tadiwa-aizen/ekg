"""Result output handling for console, JSON, and CSV formats."""

from pathlib import Path
from typing import Dict, Any
import json
import csv
from datetime import datetime


class OutputHandler:
    """Handles result output to console and files."""

    def __init__(self, output_dir: Path):
        """
        Initialize OutputHandler with output directory.

        Args:
            output_dir: Directory where output files will be saved
        """
        self.output_dir = Path(output_dir)

    def display_results(self, metrics: Dict[str, Any]) -> None:
        """
        Display results to console in readable format.

        Args:
            metrics: Dictionary containing graph metrics
        """
        print("\n" + "=" * 70)
        print("EKG EVALUATION RESULTS - PHASE 1, 2 & KGrEaT")
        print("=" * 70)
        
        # Section 1: Graph Connectivity and Cohesion
        print("\n[1] GRAPH CONNECTIVITY AND COHESION")
        print("-" * 70)
        print(f"  Total Nodes:              {metrics.get('total_nodes', 0):,}")
        print(f"  Total Edges:              {metrics.get('total_edges', 0):,}")
        print(f"  Connected Components:     {metrics.get('num_components', 0):,}")
        print(f"  Giant Component Size:     {metrics.get('giant_component_size', 0):,}")
        print(f"  Giant Component Ratio:    {metrics.get('giant_component_ratio', 0):.4f}")
        print(f"  Average Clustering:       {metrics.get('avg_clustering', 0):.4f}")
        
        edge_conn = metrics.get('edge_connectivity', 0)
        if edge_conn == -1:
            print(f"  Edge Connectivity:        N/A (calculation failed)")
        else:
            print(f"  Edge Connectivity:        {edge_conn}")
        
        # Section 2: Graph Size and Density
        print("\n[2] GRAPH SIZE AND DENSITY")
        print("-" * 70)
        print(f"  Average Degree:           {metrics.get('avg_degree', 0):.4f}")
        print(f"  Graph Density:            {metrics.get('density', 0):.6f}")
        
        # Section 3: Redundancy Analysis
        if 'redundancy' in metrics:
            red = metrics['redundancy']
            print("\n[3] REDUNDANCY AND DUPLICATION")
            print("-" * 70)
            print(f"  Total Events:             {red.get('total_events', 0):,}")
            print(f"  Exact Label Duplicates:   {red.get('exact_label_duplicates', 0):,}")
            print(f"  Duplicate Events (exact): {red.get('exact_duplicate_events', 0):,}")
            print(f"  SameAs Duplicates:        {red.get('sameas_duplicates', 0):,}")
            print(f"  Fuzzy Duplicate Pairs:    {red.get('fuzzy_duplicate_pairs', 0):,}")
            print(f"  Duplication Rate:         {red.get('duplication_rate', 0):.2f}%")
            
            # Label quality subsection
            if 'label_quality' in red:
                lq = red['label_quality']
                print("\n  Label Quality:")
                print(f"    Labels Sampled:         {lq.get('total_labels_sampled', 0):,}")
                print(f"    Unique Labels:          {lq.get('unique_labels', 0):,}")
                print(f"    Uniqueness Rate:        {lq.get('label_uniqueness_rate', 0):.2f}%")
                print(f"    Fuzzy Duplicates (90%): {lq.get('fuzzy_duplicates_90', 0):,}")
        
        # Section 4: Temporal Consistency
        if 'temporal' in metrics:
            temp = metrics['temporal']
            
            # Date format validation
            if 'date_format_validation' in temp:
                dfv = temp['date_format_validation']
                print("\n[4] TEMPORAL CONSISTENCY")
                print("-" * 70)
                print("  Date Format Validation:")
                print(f"    Sampled Events:         {dfv.get('total_sampled', 0):,}")
                print(f"    Valid ISO 8601:         {dfv.get('valid_dates', 0):,}")
                print(f"    Invalid Dates:          {dfv.get('invalid_dates', 0):,}")
                print(f"    Compliance Rate:        {dfv.get('compliance_rate', 0):.2f}%")
            
            # Temporal granularity
            if 'temporal_granularity' in temp:
                tg = temp['temporal_granularity']
                print("\n  Temporal Granularity:")
                print(f"    Sampled Events:         {tg.get('total_sampled', 0):,}")
                if 'granularity_percentages' in tg:
                    gp = tg['granularity_percentages']
                    print(f"    Year-level:             {gp.get('year', 0):.2f}%")
                    print(f"    Month-level:            {gp.get('month', 0):.2f}%")
                    print(f"    Day-level:              {gp.get('day', 0):.2f}%")
                    print(f"    Timestamp-level:        {gp.get('timestamp', 0):.2f}%")
            
            # Temporal coverage
            if 'temporal_coverage' in temp:
                tc = temp['temporal_coverage']
                print("\n  Temporal Coverage:")
                print(f"    Total Events:           {tc.get('total_events', 0):,}")
                print(f"    Events with Dates:      {tc.get('events_with_dates', 0):,}")
                print(f"    Missing Dates:          {tc.get('events_missing_dates', 0):,}")
                print(f"    Coverage Rate:          {tc.get('temporal_coverage_rate', 0):.2f}%")
            
            # Temporal density subsection
            if 'temporal_density' in temp:
                td = temp['temporal_density']
                print("\n  Temporal Density:")
                print(f"    Temporal Span:          {td.get('temporal_span_years', 0):,} years")
                print(f"    Avg Events/Decade:      {td.get('avg_events_per_decade', 0):.2f}")
                print(f"    Coverage Gaps:          {td.get('coverage_gaps', 0):,} decades")
                print(f"    Peak Decade:            {td.get('peak_decade', 'N/A')} ({td.get('peak_decade_count', 0):,} events)")
        
        # Section 5: Schema Conformance (Phase 2)
        if 'schema' in metrics:
            sch = metrics['schema']
            print("\n[5] SCHEMA ALIGNMENT & CONFORMANCE")
            print("-" * 70)
            print(f"  Total Events:             {sch.get('total_events', 0):,}")
            print(f"  Events with Labels:       {sch.get('events_with_labels', 0):,}")
            print(f"  Events with Dates:        {sch.get('events_with_dates', 0):,}")
            print(f"  Fully Described Events:   {sch.get('fully_described_events', 0):,}")
            print(f"  Label Coverage:           {sch.get('label_coverage_rate', 0):.2f}%")
            print(f"  Date Coverage:            {sch.get('date_coverage_rate', 0):.2f}%")
            print(f"  Schema Conformance:       {sch.get('schema_conformance_rate', 0):.2f}%")
            print(f"  Non-standard Properties:  {sch.get('non_standard_properties_count', 0):,}")
            if 'external_vocabulary_usage' in sch:
                ext = sch['external_vocabulary_usage']
                print(f"  External Vocab Usage:")
                for vocab, count in ext.items():
                    print(f"    {vocab}: {count:,}")
        
        # Section 6: Coverage & Completeness (Phase 2)
        if 'completeness' in metrics:
            comp = metrics['completeness']
            print("\n[6] COVERAGE & COMPLETENESS")
            print("-" * 70)
            print(f"  Total Event Instances:    {comp.get('total_event_instances', 0):,}")
            print(f"  Used Event Classes:       {comp.get('used_event_classes', 0):,}")
            print(f"  Declared Event Classes:   {comp.get('declared_event_classes', 0):,}")
            print(f"  Complete Events:          {comp.get('events_with_complete_data', 0):,}")
            print(f"  Schema Coverage:          {comp.get('schema_coverage_percentage', 0):.2f}%")
            print(f"  Population Completeness:  {comp.get('population_completeness_percentage', 0):.2f}%")
            print(f"  Class Usage Efficiency:   {comp.get('class_usage_efficiency_percentage', 0):.2f}%")
        
        # Section 7: Type Consistency (Phase 2)
        if 'type_consistency' in metrics:
            tc = metrics['type_consistency']
            print("\n[7] TYPE & ROLE CONSISTENCY")
            print("-" * 70)
            print(f"  Properties Analyzed:      {tc.get('properties_analyzed', 0):,}")
            print(f"  Properties w/ Violations: {tc.get('properties_with_violations', 0):,}")
            print(f"  Avg Domain Conformity:    {tc.get('average_domain_conformity', 0):.2f}%")
            print(f"  Avg Range Conformity:     {tc.get('average_range_conformity', 0):.2f}%")
            print(f"  Overall Type Consistency: {tc.get('overall_type_consistency', 0):.2f}%")
        
        # Section 8: Entity Richness (KGrEaT)
        if 'entity_richness' in metrics:
            er = metrics['entity_richness']
            print("\n[8] ENTITY RICHNESS")
            print("-" * 70)
            print(f"  Avg Properties/Event:     {er.get('avg_properties_per_event', 0):.2f}")
            print(f"  Median Properties/Event:  {er.get('median_properties_per_event', 0):.2f}")
            print(f"  Std Dev Properties:       {er.get('std_dev_properties', 0):.2f}")
            print(f"  Sparse Entities (<3):     {er.get('sparse_entities_percentage', 0):.2f}%")
            print(f"  Events Analyzed:          {er.get('total_events_analyzed', 0):,}")
        
        # Section 9: External Mapping Coverage (KGrEaT)
        if 'mapping_coverage' in metrics:
            mc = metrics['mapping_coverage']
            print("\n[9] EXTERNAL MAPPING COVERAGE")
            print("-" * 70)
            print(f"  Total Events:             {mc.get('total_events', 0):,}")
            print(f"  With External Links:      {mc.get('events_with_external_links', 0):,}")
            print(f"  Linked to Wikidata:       {mc.get('events_linked_to_wikidata', 0):,}")
            print(f"  Linked to DBpedia:        {mc.get('events_linked_to_dbpedia', 0):,}")
            print(f"  External Link Rate:       {mc.get('external_link_rate', 0):.2f}%")
            print(f"  Wikidata Coverage:        {mc.get('wikidata_coverage', 0):.2f}%")
            print(f"  DBpedia Coverage:         {mc.get('dbpedia_coverage', 0):.2f}%")
        
        # Section 10: Predicate Usage Patterns (KGrEaT)
        if 'predicate_usage' in metrics:
            pu = metrics['predicate_usage']
            print("\n[10] PREDICATE USAGE PATTERNS")
            print("-" * 70)
            print(f"  Total Unique Predicates:  {pu.get('total_unique_predicates', 0):,}")
            print(f"  Total Triples:            {pu.get('total_triples', 0):,}")
            print(f"  Top-10 Concentration:     {pu.get('top_10_concentration', 0):.2f}%")
            print(f"  Singleton Predicates:     {pu.get('singleton_predicates', 0):,}")
            print(f"  Gini Coefficient:         {pu.get('gini_coefficient', 0):.4f}")
        
        # Metadata
        print("\n" + "-" * 70)
        if 'timestamp' in metrics:
            print(f"Timestamp:                  {metrics['timestamp']}")
        if 'ekg_folder' in metrics:
            print(f"EKG Folder:                 {metrics['ekg_folder']}")
        
        print("=" * 70 + "\n")

    def save_json(self, metrics: Dict[str, Any]) -> Path:
        """
        Save results to JSON file with timestamp in filename.

        Args:
            metrics: Dictionary containing graph metrics

        Returns:
            Path to the saved JSON file

        Raises:
            OSError: If file cannot be written
        """
        # Create output directory if it doesn't exist
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise OSError(
                f"Permission denied: Cannot create output directory at {self.output_dir}.\n"
                f"Please check file permissions or choose a different location."
            ) from e
        except OSError as e:
            raise OSError(
                f"Failed to create output directory at {self.output_dir}.\n"
                f"Error: {str(e)}"
            ) from e
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ekg_metrics_{timestamp}.json"
        filepath = self.output_dir / filename
        
        # Write JSON file with pretty formatting
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
            return filepath
        except PermissionError as e:
            raise OSError(
                f"Permission denied: Cannot write JSON file to {filepath}.\n"
                f"Please check file permissions."
            ) from e
        except OSError as e:
            # Check for disk space issues
            if "No space left on device" in str(e) or "disk full" in str(e).lower():
                raise OSError(
                    f"Insufficient disk space to write JSON file.\n"
                    f"Output location: {filepath}\n"
                    f"Please free up disk space or choose a different output directory."
                ) from e
            else:
                raise OSError(
                    f"Failed to write JSON file {filepath}.\n"
                    f"Error: {str(e)}"
                ) from e
        except Exception as e:
            raise OSError(
                f"Unexpected error writing JSON file {filepath}.\n"
                f"Error: {str(e)}"
            ) from e

    def save_csv(self, metrics: Dict[str, Any]) -> Path:
        """
        Save results to CSV file with timestamp in filename.

        Args:
            metrics: Dictionary containing graph metrics

        Returns:
            Path to the saved CSV file

        Raises:
            OSError: If file cannot be written
        """
        # Create output directory if it doesn't exist
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            raise OSError(
                f"Permission denied: Cannot create output directory at {self.output_dir}.\n"
                f"Please check file permissions or choose a different location."
            ) from e
        except OSError as e:
            raise OSError(
                f"Failed to create output directory at {self.output_dir}.\n"
                f"Error: {str(e)}"
            ) from e
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ekg_metrics_{timestamp}.csv"
        filepath = self.output_dir / filename
        
        # Write CSV file
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow(['Metric', 'Value'])
                
                # Write metrics in a consistent order
                metric_order = [
                    'total_nodes',
                    'total_edges',
                    'num_components',
                    'giant_component_size',
                    'giant_component_ratio',
                    'avg_clustering',
                    'edge_connectivity',
                    'avg_degree',
                    'density',
                    'timestamp',
                    'ekg_folder'
                ]
                
                for key in metric_order:
                    if key in metrics:
                        writer.writerow([key, metrics[key]])
                
                # Write redundancy metrics
                if 'redundancy' in metrics:
                    writer.writerow(['--- REDUNDANCY METRICS ---', ''])
                    for key, value in metrics['redundancy'].items():
                        writer.writerow([f'redundancy.{key}', value])
                
                # Write temporal metrics
                if 'temporal' in metrics:
                    writer.writerow(['--- TEMPORAL METRICS ---', ''])
                    self._flatten_dict(writer, metrics['temporal'], 'temporal')
                
                # Write schema metrics
                if 'schema' in metrics:
                    writer.writerow(['--- SCHEMA METRICS ---', ''])
                    self._flatten_dict(writer, metrics['schema'], 'schema')
                
                # Write completeness metrics
                if 'completeness' in metrics:
                    writer.writerow(['--- COMPLETENESS METRICS ---', ''])
                    self._flatten_dict(writer, metrics['completeness'], 'completeness')
                
                # Write type consistency metrics
                if 'type_consistency' in metrics:
                    writer.writerow(['--- TYPE CONSISTENCY METRICS ---', ''])
                    self._flatten_dict(writer, metrics['type_consistency'], 'type_consistency')
                
                # Write entity richness metrics
                if 'entity_richness' in metrics:
                    writer.writerow(['--- ENTITY RICHNESS METRICS ---', ''])
                    self._flatten_dict(writer, metrics['entity_richness'], 'entity_richness')
                
                # Write mapping coverage metrics
                if 'mapping_coverage' in metrics:
                    writer.writerow(['--- MAPPING COVERAGE METRICS ---', ''])
                    self._flatten_dict(writer, metrics['mapping_coverage'], 'mapping_coverage')
                
                # Write predicate usage metrics
                if 'predicate_usage' in metrics:
                    writer.writerow(['--- PREDICATE USAGE METRICS ---', ''])
                    self._flatten_dict(writer, metrics['predicate_usage'], 'predicate_usage')
                    writer.writerow(['--- TYPE CONSISTENCY METRICS ---', ''])
                    self._flatten_dict(writer, metrics['type_consistency'], 'type_consistency')
                
                # Write any additional metrics not in the standard order
                for key, value in metrics.items():
                    if key not in metric_order and key not in ['redundancy', 'temporal', 'schema', 'completeness', 'type_consistency']:
                        if not isinstance(value, (dict, list)):
                            writer.writerow([key, value])
            
            return filepath
        except PermissionError as e:
            raise OSError(
                f"Permission denied: Cannot write CSV file to {filepath}.\n"
                f"Please check file permissions."
            ) from e
        except OSError as e:
            # Check for disk space issues
            if "No space left on device" in str(e) or "disk full" in str(e).lower():
                raise OSError(
                    f"Insufficient disk space to write CSV file.\n"
                    f"Output location: {filepath}\n"
                    f"Please free up disk space or choose a different output directory."
                ) from e
            else:
                raise OSError(
                    f"Failed to write CSV file {filepath}.\n"
                    f"Error: {str(e)}"
                ) from e
        except Exception as e:
            raise OSError(
                f"Unexpected error writing CSV file {filepath}.\n"
                f"Error: {str(e)}"
            ) from e

    def _flatten_dict(self, writer, data: Dict[str, Any], prefix: str = '') -> None:
        """Helper to flatten nested dictionaries for CSV output."""
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                self._flatten_dict(writer, value, full_key)
            elif isinstance(value, list):
                writer.writerow([full_key, str(value)])
            else:
                writer.writerow([full_key, value])
