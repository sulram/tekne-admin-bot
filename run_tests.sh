#!/bin/bash
#
# Tekne Admin Bot - Test Runner
#
# Usage:
#   ./run_tests.sh              # Run all tests
#   ./run_tests.sh agent        # Run agent tests only
#   ./run_tests.sh tools        # Run tools tests only
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🧪 Tekne Admin Bot - Test Suite"
echo "================================"
echo ""

if [ -z "$1" ] || [ "$1" == "agent" ]; then
    echo -e "${YELLOW}Running agent tests...${NC}"
    python3 tests/agent/test_model_selection.py
    echo ""
fi

if [ -z "$1" ] || [ "$1" == "tools" ]; then
    if [ -f tests/tools/test_proposal_tools.py ]; then
        echo -e "${YELLOW}Running tools tests...${NC}"
        python3 tests/tools/test_proposal_tools.py
        echo ""
    fi
fi

echo -e "${GREEN}✅ All tests completed!${NC}"
