"""CLI entry point for EKG Evaluation CLI."""

import sys
from pathlib import Path
import click

from .orchestrator import EvaluationOrchestrator, EvaluationConfig
from .config import EvaluationParameters


@click.command()
@click.argument(
    'ekg_folder',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    metavar='EKG_FOLDER'
)
@click.option(
    '--port',
    type=click.IntRange(1, 65535),
    default=3030,
    help='Fuseki port (default: 3030)'
)
@click.option(
    '--verbose',
    is_flag=True,
    help='Enable verbose output with detailed progress information'
)
@click.option(
    '--output-dir',
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help='Custom output directory for results (default: ./ekg_results)'
)
@click.option(
    '--jena-home',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help='Path to Apache Jena installation directory'
)
@click.option(
    '--fuseki-home',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help='Path to Apache Jena Fuseki installation directory'
)
@click.option(
    '--fuzzy-threshold',
    type=float,
    default=0.90,
    help='Exact token-sort similarity threshold (0.0-1.0, default: 0.90)'
)
@click.option(
    '--fuzzy-sample-size',
    type=int,
    default=1000,
    help='Maximum deterministic event sample for exact fuzzy matching (default: 1000)'
)
@click.option(
    '--temporal-sample-size',
    type=int,
    default=1000,
    help='Number of temporal relations to sample (default: 1000)'
)
@click.option(
    '--max-properties',
    type=int,
    default=50,
    help='Maximum properties to analyze for type consistency (default: 50)'
)
@click.option(
    '--large-graph-mode',
    is_flag=True,
    help='Use DuckDB and streaming union-find for structural metrics instead of NetworkX'
)
@click.option(
    '--graph-structure-only',
    is_flag=True,
    help='Only compute graph structural metrics; skip endpoint-based RDF quality metrics'
)
@click.option(
    '--large-graph-work-dir',
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help='Work directory for large graph artefacts (default: OUTPUT_DIR/large_graph_work)'
)
@click.option(
    '--duckdb-memory-limit',
    type=str,
    default='8GB',
    help='DuckDB memory limit for large graph mode (default: 8GB)'
)
@click.option(
    '--duckdb-temp-dir',
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=None,
    help='DuckDB temporary spill directory for large graph mode'
)
@click.version_option(
    version='0.2.0',
    prog_name='ekg-eval-cli',
    message='%(prog)s version %(version)s'
)
def main(ekg_folder, verbose, output_dir, jena_home, fuseki_home,
         port, fuzzy_threshold, fuzzy_sample_size, temporal_sample_size, max_properties,
         large_graph_mode, graph_structure_only, large_graph_work_dir,
         duckdb_memory_limit, duckdb_temp_dir):
    """
    Evaluate an RDF-based event-centric knowledge graph as a
    multidimensional intrinsic quality profile.

    EKG_FOLDER is the path to a directory containing N-Triples (.nt) files
    representing your Event-Centric Knowledge Graph.

    The tool will:
    \b
    1. Load the .nt files into a TDB2 database (if not already loaded)
    2. Start Apache Jena Fuseki SPARQL server (if not already running)
    3. Extract graph edges
    4. Calculate connectivity and cohesion metrics using NetworkX or large graph mode
    5. Output results to console, JSON, and CSV files

    Examples:

    \b
    # Basic usage
    $ ekg-eval-cli /path/to/ekg/folder

    \b
    # With verbose output
    $ ekg-eval-cli /path/to/ekg/folder --verbose

    \b
    # With custom parameters
    $ ekg-eval-cli /path/to/ekg/folder --fuzzy-threshold 0.90 --max-properties 100

    \b
    # With custom Jena and Fuseki paths
    $ ekg-eval-cli /path/to/ekg/folder --jena-home /opt/jena --fuseki-home /opt/fuseki
    """
    # Set default output directory if not provided
    if output_dir is None:
        output_dir = Path.cwd() / "ekg_results"

    # Create evaluation parameters
    try:
        params = EvaluationParameters(
            fuzzy_similarity_threshold=fuzzy_threshold,
            fuzzy_sample_size=fuzzy_sample_size,
            temporal_sample_size=temporal_sample_size,
            max_properties_analyzed=max_properties
        )
        params.validate()
    except ValueError as e:
        click.echo(f"\n❌ Invalid parameter: {str(e)}", err=True)
        sys.exit(1)

    # Create configuration
    config = EvaluationConfig(
        ekg_folder=ekg_folder,
        output_dir=output_dir,
        jena_home=jena_home,
        fuseki_home=fuseki_home,
        verbose=verbose,
        port=port,
        large_graph_mode=large_graph_mode,
        graph_structure_only=graph_structure_only,
        large_graph_work_dir=large_graph_work_dir,
        duckdb_memory_limit=duckdb_memory_limit,
        duckdb_temp_dir=duckdb_temp_dir,
        parameters=params
    )

    # Display startup message
    if verbose:
        click.echo("=" * 70)
        click.echo("EKG Evaluation CLI v0.2.0")
        click.echo("=" * 70)
        click.echo(f"EKG Folder: {ekg_folder.absolute()}")
        click.echo(f"Output Directory: {output_dir.absolute()}")
        if jena_home:
            click.echo(f"Jena Home: {jena_home.absolute()}")
        if fuseki_home:
            click.echo(f"Fuseki Home: {fuseki_home.absolute()}")
        if large_graph_mode:
            click.echo("Large Graph Mode: enabled")
            if large_graph_work_dir:
                click.echo(f"Large Graph Work Dir: {large_graph_work_dir.absolute()}")
            click.echo(f"DuckDB Memory Limit: {duckdb_memory_limit}")
            if duckdb_temp_dir:
                click.echo(f"DuckDB Temp Dir: {duckdb_temp_dir.absolute()}")
        if graph_structure_only:
            click.echo("Graph Structure Only: enabled")
        click.echo("=" * 70)
        click.echo()

    # Create and run orchestrator
    try:
        orchestrator = EvaluationOrchestrator(config)
        metrics = orchestrator.run()

        # Success message
        if verbose:
            click.echo()
            click.echo("=" * 70)
            click.echo("Evaluation completed successfully!")
            click.echo("=" * 70)
        
        sys.exit(0)

    except FileNotFoundError as e:
        # User error - missing files or paths
        click.echo(f"\n❌ Error: {str(e)}", err=True)
        if verbose:
            click.echo("\nThis is a user error (exit code 1).", err=True)
            import traceback
            traceback.print_exc()
        sys.exit(1)

    except ValueError as e:
        # User error - invalid input
        click.echo(f"\n❌ Error: {str(e)}", err=True)
        if verbose:
            click.echo("\nThis is a user error (exit code 1).", err=True)
            import traceback
            traceback.print_exc()
        sys.exit(1)

    except RuntimeError as e:
        # System error - tool execution failure
        click.echo(f"\n❌ Error: {str(e)}", err=True)
        if verbose:
            click.echo("\nThis is a system error (exit code 2).", err=True)
            import traceback
            traceback.print_exc()
        sys.exit(2)

    except OSError as e:
        # System error - file I/O failure
        click.echo(f"\n❌ Error: {str(e)}", err=True)
        if verbose:
            click.echo("\nThis is a system error (exit code 2).", err=True)
            import traceback
            traceback.print_exc()
        sys.exit(2)

    except KeyboardInterrupt:
        # User interrupted
        click.echo("\n\n⚠️  Evaluation interrupted by user.", err=True)
        if verbose:
            click.echo("Resources have been cleaned up.", err=True)
        sys.exit(1)

    except Exception as e:
        # Unexpected error
        click.echo(f"\n❌ Unexpected error: {str(e)}", err=True)
        click.echo("This is an unexpected error. Please report this issue.", err=True)
        if verbose:
            click.echo("\nFull stack trace:", err=True)
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    main()
