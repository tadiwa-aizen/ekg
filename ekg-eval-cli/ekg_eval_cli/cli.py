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
    default=0.85,
    help='Fuzzy matching similarity threshold (0.0-1.0, default: 0.85)'
)
@click.option(
    '--fuzzy-sample-size',
    type=int,
    default=1000,
    help='Number of events to sample for fuzzy matching (default: 1000)'
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
@click.version_option(
    version='0.1.0',
    prog_name='ekg-eval-cli',
    message='%(prog)s version %(version)s'
)
def main(ekg_folder, verbose, output_dir, jena_home, fuseki_home,
         fuzzy_threshold, fuzzy_sample_size, temporal_sample_size, max_properties):
    """
    Evaluate Event-Centric Knowledge Graph structural metrics.

    EKG_FOLDER is the path to a directory containing N-Triples (.nt) files
    representing your Event-Centric Knowledge Graph.

    The tool will:
    \b
    1. Load the .nt files into a TDB2 database (if not already loaded)
    2. Start Apache Jena Fuseki SPARQL server (if not already running)
    3. Extract graph edges using SPARQL queries
    4. Calculate connectivity and cohesion metrics using NetworkX
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
        parameters=params
    )

    # Display startup message
    if verbose:
        click.echo("=" * 70)
        click.echo("EKG Evaluation CLI v0.1.0")
        click.echo("=" * 70)
        click.echo(f"EKG Folder: {ekg_folder.absolute()}")
        click.echo(f"Output Directory: {output_dir.absolute()}")
        if jena_home:
            click.echo(f"Jena Home: {jena_home.absolute()}")
        if fuseki_home:
            click.echo(f"Fuseki Home: {fuseki_home.absolute()}")
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
