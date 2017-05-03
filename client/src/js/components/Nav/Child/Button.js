/**
 * @license
 * The MIT License (MIT)
 * Copyright 2015 Government of Canada
 *
 * @author
 * Ian Boyes
 *
 * @exports ChildButton
 */

import React from "react";
import CX from "classnames";
import { capitalize } from "lodash";

/**
 * The button for a secondary navbar which renders a single child route of a primary route.
 */
export default class ChildButton extends React.Component {

    static propTypes = {
        label: React.PropTypes.string,
        childKey: React.PropTypes.string,
        active: React.PropTypes.bool
    };

    /**
     * Change the secondary route in the router in response to a click event on the button.
     * @func
     */
    handleClick = () => {
        window.router.setChild(this.props.childKey);
    };

    render = () => (
        <li className={CX("pointer", {active: this.props.active})} onClick={this.handleClick}>
            <a>{this.props.label || capitalize(this.props.childKey)}</a>
        </li>
    );
}
