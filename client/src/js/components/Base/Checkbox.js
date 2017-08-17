/**
 * @license
 * The MIT License (MIT)
 * Copyright 2015 Government of Canada
 *
 * @author
 * Ian Boyes
 *
 * @exports Checkbox
 */

import CX from "classnames";
import React from "react";

/**
 * A checkbox component based on the Icomoon checkbox icons. Has three possible states: checked, unchecked, and partial.
 * The appearance is set with two props: checked and partial. Takes an onClick prop which is a function to call when
 * the checkbox is clicked.
 *
 * @class
 *
 */
export const Checkbox = (props) => {

    let name = "unchecked";

    if (props.checked) {
        name = "checked";
    } else {
        if (props.partial) {
            name = "partial";
        }
    }

    let className = CX("pointer", {
        "pull-right": props.pullRight,
        "labelled-checkbox": props.label
    });

    if (props.className) {
        className += " " + props.className;
    }

    return (
        <span className={className} onClick={props.onClick} style={props.style}>
            <i className={`i-checkbox-${name}`} /> {props.label ? <span>{props.label}</span>: null}
        </span>
    );
};

Checkbox.propTypes = {
    label: React.PropTypes.node,
    checked: React.PropTypes.bool,
    partial: React.PropTypes.bool,
    onClick: React.PropTypes.func,
    pending: React.PropTypes.bool,
    style: React.PropTypes.object,
    className: React.PropTypes.string,
    pullRight: React.PropTypes.bool
};

Checkbox.defaultProps = {
    checked: false,
    partial: false,
    pullRight: false
};
