#!/bin/bash
# Quick test runner script

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Device Manager Backend Test Suite${NC}\n"

# Parse arguments
TEST_ARGS="${@:-.}"  # Default to run all tests if no args provided

case "$1" in
    unit)
        echo -e "${BLUE}Running unit tests...${NC}"
        docker-compose run --rm test pytest tests/ -m unit -v
        ;;
    integration)
        echo -e "${BLUE}Running integration tests...${NC}"
        docker-compose run --rm test pytest tests/ -m integration -v
        ;;
    coverage)
        echo -e "${BLUE}Running tests with coverage...${NC}"
        docker-compose run --rm test pytest tests/ -v --cov=app --cov-report=html --cov-report=term
        echo -e "${GREEN}Coverage report generated in htmlcov/index.html${NC}"
        ;;
    *)
        echo -e "${BLUE}Running all tests...${NC}"
        docker-compose run --rm test pytest tests/ -v "$@"
        ;;
esac

echo -e "\n${GREEN}✓ Tests completed!${NC}"
