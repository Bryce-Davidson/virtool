import { get } from "lodash-es";
import React from "react";
import { connect } from "react-redux";
import { Box, Container, Icon } from "../../base";

export const Welcome = props => {
    let version;

    if (props.version) {
        version = <small className="text-muted">{props.version}</small>;
    }
    return (
        <Container>
            <Box>
                <h3>Virtool {version}</h3>
                <p>Viral infection diagnostics using next-generation sequencing</p>

                <a className="btn btn-default" href="http://www.virtool.ca/" target="_blank" rel="noopener noreferrer">
                    <Icon name="globe" /> Website
                </a>
            </Box>
        </Container>
    );
};

export const mapStateToProps = state => ({
    version: get(state.updates, "version")
});

export default connect(
    mapStateToProps,
    null
)(Welcome);
